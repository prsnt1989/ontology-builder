"""FastAPI application for Ontology Builder."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from .config import settings
from .session_store import session_store
from .intake.specialist import IntakeSpecialist
from .research.specialist import ResearchSpecialist
from .ontology_designer.specialist import OntologyDesignerSpecialist
from .actions_rules.specialist import ActionsRulesSpecialist
from .validator.specialist import ValidatorSpecialist
from .ontology_qa.specialist import OntologyQASpecialist
from .datastore.sqlite_backend import SQLiteBackend
from .datastore.schema_generator import ontology_to_table_definitions, generate_ddl
from .datastore.migration_manager import MigrationManager
from .datastore.seed_generator import seed_database
from .shared.yaml_writer import write_ontology_files
from .shared.schemas import OntologyMeta
from .ontology_registry.registry import registry

datastore: Optional[SQLiteBackend] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global datastore
    datastore = SQLiteBackend(settings.db_path)
    await datastore.initialize()

    migration_mgr = MigrationManager(datastore)
    await migration_mgr.initialize()

    yield

    if datastore:
        await datastore.close()


app = FastAPI(title="Ontology Builder", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- MAF pipeline workflow over AG-UI (SSE) ---

from agent_framework.ag_ui import add_agent_framework_fastapi_endpoint  # noqa: E402
from .workflow.ag_ui_app import PipelineAGUIWorkflow  # noqa: E402
from .workflow.update_ag_ui_app import UpdatePipelineAGUIWorkflow  # noqa: E402


def _get_datastore() -> SQLiteBackend:
    if datastore is None:
        raise RuntimeError("Datastore not initialized")
    return datastore


add_agent_framework_fastapi_endpoint(
    app=app,
    agent=PipelineAGUIWorkflow(datastore_getter=_get_datastore),
    path="/api/pipeline",
)

add_agent_framework_fastapi_endpoint(
    app=app,
    agent=UpdatePipelineAGUIWorkflow(datastore_getter=_get_datastore),
    path="/api/pipeline/update",
)


# --- Request/Response Models ---

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    mode: str = "build"  # "build" | "qa" | "update"


class ChatResponse(BaseModel):
    session_id: str
    response: str
    phase: str
    progress: Optional[dict] = None
    specialist_data: Optional[dict] = None
    ontology_ready: bool = False


class AskRequest(BaseModel):
    question: str
    session_id: str


class AskResponse(BaseModel):
    answer: str
    sql: str = ""
    explanation: str = ""
    object_types_used: list[str] = []
    summary_table: Optional[dict] = None
    insights: list[str] = []
    follow_up_questions: list[str] = []
    row_count: int = 0


# --- Chat Endpoint (Main Pipeline) ---

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    session_id, session = session_store.get_or_create(req.session_id)
    session_store.add_message(session_id, "user", req.message)
    phase = session["phase"]

    # Enter the update flow: from a ready ontology (qa), mode="update" begins gathering changes.
    if req.mode == "update" and phase in ("qa", "complete"):
        session_store.update(session_id, "phase", "update_intake")
        session_store.update(session_id, "update_state", None)  # fresh change list
        phase = "update_intake"

    if phase == "update_intake":
        result = await _handle_update_intake(session_id, req.message)
    elif req.mode == "qa" or phase == "qa":
        return await _handle_qa(session_id, req.message)
    elif phase == "intake":
        result = await _handle_intake(session_id, req.message)
    elif phase == "research":
        result = await _handle_research(session_id)
    elif phase == "design":
        result = await _handle_design(session_id)
    elif phase == "actions_rules":
        result = await _handle_actions_rules(session_id)
    elif phase == "validation":
        result = await _handle_validation(session_id)
    elif phase == "generating":
        result = await _handle_generation(session_id)
    elif phase == "complete":
        session_store.update(session_id, "phase", "qa")
        result = await _handle_qa(session_id, req.message)
        return result
    else:
        result = {"response": "Unknown phase.", "phase": phase}

    session_store.add_message(session_id, "assistant", result.get("response", ""))

    # An already-generated ontology stays "ready" throughout the update flow so the
    # UI keeps the ontology-dependent views/nav unlocked.
    already_generated = bool(session_store.get_value(session_id, "generated_files"))

    return ChatResponse(
        session_id=session_id,
        response=result.get("response", ""),
        phase=session_store.get_value(session_id, "phase") or phase,
        progress=result.get("progress"),
        specialist_data=result.get("output"),
        ontology_ready=result.get("ontology_ready", already_generated),
    )


async def _handle_intake(session_id: str, message: str) -> dict[str, Any]:
    specialist = IntakeSpecialist()
    result = await specialist.analyze(session_id, message)
    return result


async def _handle_update_intake(session_id: str, message: str) -> dict[str, Any]:
    from .update_intake.specialist import UpdateIntakeSpecialist

    specialist = UpdateIntakeSpecialist()
    return await specialist.analyze(session_id, message)


async def _handle_research(session_id: str) -> dict[str, Any]:
    specialist = ResearchSpecialist()
    result = await specialist.analyze(session_id)
    return result


async def _handle_design(session_id: str) -> dict[str, Any]:
    specialist = OntologyDesignerSpecialist()
    result = await specialist.analyze(session_id)
    return result


async def _handle_actions_rules(session_id: str) -> dict[str, Any]:
    specialist = ActionsRulesSpecialist()
    result = await specialist.analyze(session_id)
    return result


async def _handle_validation(session_id: str) -> dict[str, Any]:
    specialist = ValidatorSpecialist()
    result = await specialist.analyze(session_id)
    return result


async def _handle_generation(session_id: str) -> dict[str, Any]:
    """Generate YAML files, create DB tables, seed data."""
    global datastore
    ontology = session_store.get_value(session_id, "ontology_design")
    actions_rules = session_store.get_value(session_id, "actions_rules")
    intake = session_store.get_value(session_id, "intake_output")

    if not ontology or not actions_rules:
        return {"response": "Missing ontology data for generation.", "phase": "error"}

    # Build meta
    company_name = intake.get("company_profile", {}).get("company_name", "Unknown") if intake else "Unknown"
    company_slug = company_name.lower().replace(" ", "_")[:20]
    meta = OntologyMeta(
        id=f"ont_{company_slug}",
        version="1.0",
        extends=None,
        use_case=None,
        company=company_name,
        created_at=datetime.now(timezone.utc).isoformat(),
        base_version="1.0",
    )

    # Write YAML files
    object_types = [ot.copy() for ot in ontology.get("object_types", [])]
    files = write_ontology_files(
        session_id=session_id,
        meta=meta,
        object_types=object_types,
        relationships=ontology.get("relationships", []),
        actions=actions_rules.get("actions", []),
        permissions=actions_rules.get("permissions", []),
        validation_rules=actions_rules.get("validation_rules", []),
        lifecycles=actions_rules.get("lifecycles", []),
    )

    # Create database tables
    table_defs = ontology_to_table_definitions(
        ontology.get("object_types", []),
        ontology.get("relationships", []),
    )

    for td in table_defs:
        await datastore.create_table(td)

    # Track migration
    ddl = generate_ddl(table_defs)
    migration_mgr = MigrationManager(datastore)
    await migration_mgr.apply_migration("1.0", ddl)

    # Seed with synthetic data
    seed_context = ""
    if intake:
        industry = intake.get('company_profile', {}).get('industry', '')
        domain = intake.get('business_domain', {}).get('department', '')
        entities = intake.get('business_domain', {}).get('key_entities', [])
        seed_context = f"Industry: {industry}. Domain: {domain}. Key entities: {', '.join(entities)}"

    try:
        seed_counts = await seed_database(datastore, table_defs, seed_context)
    except Exception as e:
        logger.error("Seed generation failed: %s", e, exc_info=True)
        seed_counts = {}

    session_store.update(session_id, "generated_files", files)
    session_store.update(session_id, "ontology_meta", meta.model_dump())
    session_store.update(session_id, "phase", "qa")

    total_rows = sum(seed_counts.values())

    # Generate business-focused follow-up questions from the actual ontology
    suggestions = _generate_business_questions(ontology, intake)

    return {
        "response": (
            f"Ontology generation complete!\n\n"
            f"**Generated files:**\n"
            + "\n".join([f"- {name}" for name in files.keys()])
            + f"\n\n**Database:** {len(table_defs)} tables created with {total_rows} rows of synthetic data.\n\n"
            f"You can now ask questions about your data to test the ontology. Try asking:\n"
            + "\n".join([f"- \"{q}\"" for q in suggestions])
        ),
        "phase": "qa",
        "ontology_ready": True,
        "output": {
            "files": list(files.keys()),
            "tables_created": [td.table_name for td in table_defs],
            "seed_counts": seed_counts,
            "follow_up_questions": suggestions,
        },
    }


def _generate_business_questions(ontology: dict, intake: dict | None) -> list[str]:
    """Generate domain-specific questions based on the actual ontology."""
    object_types = ontology.get("object_types", [])
    relationships = ontology.get("relationships", [])

    if not object_types:
        return ["How many records are in each table?"]

    questions = []

    # Find types with status/lifecycle fields
    stateful_types = []
    for ot in object_types:
        props = ot.get("properties", [])
        if any(p.get("name") in ("status", "state", "lifecycle_state") for p in props):
            stateful_types.append(ot.get("display_name", ot.get("api_name")))

    if stateful_types:
        questions.append(f"What is the status distribution across all {stateful_types[0]}s?")

    # Find types with relationships for cross-entity queries
    if relationships and len(object_types) >= 2:
        rel = relationships[0]
        from_type = rel.get("from_object_type", "")
        to_type = rel.get("to_object_type", "")
        from_display = next((ot.get("display_name", from_type) for ot in object_types if ot.get("api_name") == from_type), from_type)
        to_display = next((ot.get("display_name", to_type) for ot in object_types if ot.get("api_name") == to_type), to_type)
        questions.append(f"Which {from_display} has the most {to_display}s?")

    # Priority/severity queries
    for ot in object_types:
        props = ot.get("properties", [])
        for p in props:
            if p.get("name") in ("priority", "severity", "risk_level"):
                questions.append(f"Show me all high priority {ot.get('display_name', ot.get('api_name'))}s")
                break
        if len(questions) >= 3:
            break

    # Business process question from intake
    if intake:
        processes = intake.get("business_domain", {}).get("key_processes", [])
        if processes:
            questions.append(f"Give me an overview of the {processes[0]} pipeline")

    # Always include a summary question
    if len(questions) < 4:
        questions.append(f"How many {object_types[0].get('display_name', 'records')}s are in each status?")

    return questions[:5]


async def _handle_qa(session_id: str, question: str) -> ChatResponse:
    global datastore
    specialist = OntologyQASpecialist(datastore)
    result = await specialist.ask(session_id, question)

    return ChatResponse(
        session_id=session_id,
        response=result.get("response", ""),
        phase="qa",
        specialist_data={
            "sql": result.get("sql", ""),
            "explanation": result.get("explanation", ""),
            "object_types_used": result.get("object_types_used", []),
            "summary_table": result.get("summary_table"),
            "insights": result.get("insights", []),
            "follow_up_questions": result.get("follow_up_questions", []),
            "row_count": result.get("row_count", 0),
        },
        ontology_ready=True,
    )


# --- Ontology Management Endpoints ---

@app.get("/api/sessions")
async def list_sessions():
    """List all existing sessions with metadata."""
    return {"sessions": session_store.list_sessions()}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    deleted = session_store.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "ontology-builder"}


@app.get("/api/skills")
async def list_skills():
    """Advertised agent skills (progressive-disclosure) for the skills panel."""
    from .skills import list_advertised_skills

    return {"skills": list_advertised_skills()}


@app.get("/api/session/{session_id}/state")
async def get_session_state(session_id: str):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session_id,
        "phase": session["phase"],
        "intake_complete": session["intake_output"] is not None,
        "research_complete": session["research_output"] is not None,
        "ontology_ready": session["generated_files"] is not None and len(session["generated_files"]) > 0,
    }


@app.get("/api/ontology/{session_id}")
async def get_ontology(session_id: str):
    ontology = registry.get_ontology(session_id)
    if not ontology:
        raise HTTPException(status_code=404, detail="Ontology not found")
    return ontology


@app.get("/api/ontology/{session_id}/graph")
async def get_ontology_graph(session_id: str):
    """Return the structured ontology design for graph visualization.

    Uses the in-memory ``ontology_design`` ({object_types, relationships}) which
    keeps properties inline and is available from the ``actions_rules`` phase
    onward (earlier than the generated YAML files).
    """
    design = session_store.get_value(session_id, "ontology_design")
    if not design or not design.get("object_types"):
        raise HTTPException(status_code=404, detail="No ontology to visualize yet")
    return {
        "object_types": design.get("object_types", []),
        "relationships": design.get("relationships", []),
    }


@app.get("/api/ontology/{session_id}/versions")
async def get_versions(session_id: str):
    session = session_store.get_session(session_id)
    if not session or not session.get("ontology_meta"):
        raise HTTPException(status_code=404, detail="Session not found")
    company_id = session["ontology_meta"].get("id", "").replace("ont_", "")
    return registry.get_versions(company_id)


@app.get("/api/ontology/{session_id}/files")
async def list_ontology_files(session_id: str):
    """List all generated YAML files for a session."""
    output_dir = Path(settings.output_dir) / session_id
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="No generated files found for this session")
    files = []
    for f in sorted(output_dir.iterdir()):
        if f.suffix in (".yaml", ".yml"):
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
            })
    return {"files": files, "session_id": session_id}


@app.get("/api/ontology/{session_id}/files/{filename}")
async def get_ontology_file(session_id: str, filename: str):
    """Get the content of a specific YAML file."""
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    filepath = Path(settings.output_dir) / session_id / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    content = filepath.read_text()
    return PlainTextResponse(content, media_type="text/yaml")


@app.post("/api/ontology/{session_id}/ask", response_model=AskResponse)
async def ask_ontology(session_id: str, req: AskRequest):
    global datastore
    specialist = OntologyQASpecialist(datastore)
    result = await specialist.ask(session_id, req.question)

    if result.get("type") == "error":
        error_msg = result.get("response", "Error processing question")
        sql = result.get("sql", "")
        return AskResponse(
            answer=f"Sorry, I couldn't answer that question. {error_msg}",
            sql=sql,
            explanation=result.get("explanation", ""),
            object_types_used=[],
            summary_table=None,
            insights=[],
            follow_up_questions=["What is the status distribution across all products?", "How many records are in each table?", "Show me the most recent entries"],
            row_count=0,
        )

    return AskResponse(
        answer=result.get("response", ""),
        sql=result.get("sql", ""),
        explanation=result.get("explanation", ""),
        object_types_used=result.get("object_types_used", []),
        summary_table=result.get("summary_table"),
        insights=result.get("insights", []),
        follow_up_questions=result.get("follow_up_questions", []),
        row_count=result.get("row_count", 0),
    )


# --- Data Access Endpoints ---

@app.get("/api/data/{session_id}/tables")
async def list_tables(session_id: str):
    global datastore
    tables = await datastore.list_tables()
    result = []
    for t in tables:
        schema = await datastore.get_schema(t)
        result.append({
            "table_name": t,
            "column_count": len(schema.columns) if schema else 0,
            "row_count": schema.row_count if schema else 0,
        })
    return {"tables": result}


@app.get("/api/data/{session_id}/tables/{table_name}")
async def get_table_data(session_id: str, table_name: str, limit: int = 50, offset: int = 0):
    global datastore
    tables = await datastore.list_tables()
    if table_name not in tables:
        raise HTTPException(status_code=404, detail="Table not found")
    rows = await datastore.query(f'SELECT * FROM "{table_name}" LIMIT {limit} OFFSET {offset}')
    schema = await datastore.get_schema(table_name)
    return {
        "table_name": table_name,
        "columns": [c.name for c in schema.columns] if schema else [],
        "rows": rows,
        "total_rows": schema.row_count if schema else 0,
    }


@app.get("/api/data/{session_id}/schema")
async def get_db_schema(session_id: str):
    global datastore
    tables = await datastore.list_tables()
    schemas = {}
    for t in tables:
        schema = await datastore.get_schema(t)
        if schema:
            schemas[t] = {
                "columns": [c.model_dump() for c in schema.columns],
                "row_count": schema.row_count,
            }
    return {"schemas": schemas}


@app.post("/api/data/{session_id}/query")
async def execute_query(session_id: str, body: dict):
    global datastore
    sql = body.get("sql", "")
    if not sql:
        raise HTTPException(status_code=400, detail="No SQL provided")
    # Only allow SELECT queries for safety
    if not sql.strip().upper().startswith("SELECT"):
        raise HTTPException(status_code=400, detail="Only SELECT queries are allowed")
    try:
        rows = await datastore.query(sql)
        return {"rows": rows, "count": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
