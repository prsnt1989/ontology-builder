"""Ontology generation: YAML file writing, DB table provisioning, and seeding.

Extracted from ``main.py`` so both the legacy ``/api/chat`` handler and the MAF
pipeline workflow executor can share one implementation. Split into two parts so
the irreversible database step can be gated behind a human-in-the-loop approval:

- :func:`write_ontology_yaml` — pure file generation (safe, idempotent).
- :func:`provision_and_seed_database` — creates tables + seeds synthetic data
  (irreversible; gated behind approval in the workflow).
- :func:`generate_business_questions` — suggested Q&A prompts from the ontology.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .session_store import session_store
from .datastore.sqlite_backend import SQLiteBackend
from .datastore.schema_generator import ontology_to_table_definitions, generate_ddl
from .datastore.migration_manager import MigrationManager
from .datastore.seed_generator import seed_database
from .shared.yaml_writer import write_ontology_files
from .shared.schemas import OntologyMeta

logger = logging.getLogger(__name__)


def _company_name(intake: dict | None) -> str:
    if not intake:
        return "Unknown"
    return intake.get("company_profile", {}).get("company_name", "Unknown")


def _next_version(current: str | None) -> str:
    """Bump the minor version (e.g. '1.0' -> '1.1'); default to '1.0'."""
    if not current:
        return "1.0"
    try:
        major, minor = current.split(".")[:2]
        return f"{major}.{int(minor) + 1}"
    except (ValueError, IndexError):
        return "1.0"


def write_ontology_yaml(session_id: str, bump_version: bool = False) -> dict[str, str]:
    """Write the 8 ontology YAML files for a session. Returns {filename: path}.

    When ``bump_version`` is True (used by the update flow), the ontology_meta
    version is incremented and ``extends``/``base_version`` reference the prior
    version, so updates are versioned.
    """
    ontology = session_store.get_value(session_id, "ontology_design")
    actions_rules = session_store.get_value(session_id, "actions_rules")
    intake = session_store.get_value(session_id, "intake_output")

    if not ontology or not actions_rules:
        raise ValueError("Missing ontology or actions/rules data for generation.")

    company_name = _company_name(intake)
    company_slug = company_name.lower().replace(" ", "_")[:20]

    prev_meta = session_store.get_value(session_id, "ontology_meta") or {}
    prev_version = prev_meta.get("version") if bump_version else None
    version = _next_version(prev_version) if bump_version else "1.0"
    meta = OntologyMeta(
        id=f"ont_{company_slug}",
        version=version,
        extends=prev_version if bump_version else None,
        use_case=None,
        company=company_name,
        created_at=datetime.now(timezone.utc).isoformat(),
        base_version=prev_meta.get("base_version", "1.0") if bump_version else "1.0",
    )

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

    session_store.update(session_id, "generated_files", files)
    session_store.update(session_id, "ontology_meta", meta.model_dump())
    return files


async def provision_and_seed_database(
    session_id: str, datastore: SQLiteBackend
) -> dict[str, Any]:
    """Create DB tables from the ontology and seed synthetic data (irreversible).

    Returns {"tables_created": [...], "seed_counts": {...}}.
    """
    ontology = session_store.get_value(session_id, "ontology_design")
    intake = session_store.get_value(session_id, "intake_output")
    if not ontology:
        raise ValueError("Missing ontology design for provisioning.")

    table_defs = ontology_to_table_definitions(
        ontology.get("object_types", []),
        ontology.get("relationships", []),
    )

    for td in table_defs:
        await datastore.create_table(td)

    ddl = generate_ddl(table_defs)
    migration_mgr = MigrationManager(datastore)
    await migration_mgr.apply_migration("1.0", ddl)

    seed_context = ""
    if intake:
        industry = intake.get("company_profile", {}).get("industry", "")
        domain = intake.get("business_domain", {}).get("department", "")
        entities = intake.get("business_domain", {}).get("key_entities", [])
        seed_context = f"Industry: {industry}. Domain: {domain}. Key entities: {', '.join(entities)}"

    try:
        seed_counts = await seed_database(datastore, table_defs, seed_context)
    except Exception as e:  # noqa: BLE001
        logger.error("Seed generation failed: %s", e, exc_info=True)
        seed_counts = {}

    return {
        "tables_created": [td.table_name for td in table_defs],
        "seed_counts": seed_counts,
    }


async def apply_ontology_updates_to_db(
    session_id: str, datastore: SQLiteBackend
) -> dict[str, Any]:
    """Apply ontology changes to the live DB ADDITIVELY (data-safe).

    - Genuinely-new tables → created and seeded.
    - Existing tables with new columns → ``ALTER TABLE ADD COLUMN`` (nullable), NOT re-seeded.
    - Removed columns/tables in the ontology are NOT dropped (existing data preserved).

    Returns {"tables_created": [...], "columns_added": {table: [cols]}, "seed_counts": {...}}.
    """
    ontology = session_store.get_value(session_id, "ontology_design")
    intake = session_store.get_value(session_id, "intake_output")
    if not ontology:
        raise ValueError("Missing ontology design for update provisioning.")

    target_defs = ontology_to_table_definitions(
        ontology.get("object_types", []),
        ontology.get("relationships", []),
    )

    existing_tables = set(await datastore.list_tables())

    new_defs = [td for td in target_defs if td.table_name not in existing_tables]
    existing_defs = [td for td in target_defs if td.table_name in existing_tables]

    # 1. Create genuinely-new tables.
    for td in new_defs:
        await datastore.create_table(td)

    # 2. ALTER existing tables to add new columns.
    columns_added: dict[str, list[str]] = {}
    for td in existing_defs:
        schema = await datastore.get_schema(td.table_name)
        existing_cols = {c.name for c in schema.columns} if schema else set()
        for col in td.columns:
            if col.name in existing_cols or col.primary_key:
                continue
            # New column: add as nullable so existing rows remain valid.
            parts = [f'ALTER TABLE "{td.table_name}" ADD COLUMN "{col.name}" {col.sql_type}']
            if col.default is not None:
                parts.append(f"DEFAULT {col.default}")
            ddl = " ".join(parts)
            try:
                await datastore.execute_ddl(ddl)
                columns_added.setdefault(td.table_name, []).append(col.name)
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to add column %s.%s: %s", td.table_name, col.name, e)

    # 3. Seed ONLY the new tables (never re-seed existing → no duplicate rows).
    seed_counts: dict[str, int] = {}
    if new_defs:
        seed_context = ""
        if intake:
            industry = intake.get("company_profile", {}).get("industry", "")
            domain = intake.get("business_domain", {}).get("department", "")
            entities = intake.get("business_domain", {}).get("key_entities", [])
            seed_context = f"Industry: {industry}. Domain: {domain}. Key entities: {', '.join(entities)}"
        try:
            seed_counts = await seed_database(datastore, new_defs, seed_context)
        except Exception as e:  # noqa: BLE001
            logger.error("Seed generation failed for new tables: %s", e, exc_info=True)
            seed_counts = {}

    return {
        "tables_created": [td.table_name for td in new_defs],
        "columns_added": columns_added,
        "seed_counts": seed_counts,
    }


def generate_business_questions(ontology: dict, intake: dict | None) -> list[str]:
    """Generate domain-specific suggested questions from the actual ontology."""
    object_types = ontology.get("object_types", [])
    relationships = ontology.get("relationships", [])

    if not object_types:
        return ["How many records are in each table?"]

    questions: list[str] = []

    stateful_types = []
    for ot in object_types:
        props = ot.get("properties", [])
        if any(p.get("name") in ("status", "state", "lifecycle_state") for p in props):
            stateful_types.append(ot.get("display_name", ot.get("api_name")))

    if stateful_types:
        questions.append(f"What is the status distribution across all {stateful_types[0]}s?")

    if relationships and len(object_types) >= 2:
        rel = relationships[0]
        from_type = rel.get("from_object_type", "")
        to_type = rel.get("to_object_type", "")
        from_display = next(
            (ot.get("display_name", from_type) for ot in object_types if ot.get("api_name") == from_type),
            from_type,
        )
        to_display = next(
            (ot.get("display_name", to_type) for ot in object_types if ot.get("api_name") == to_type),
            to_type,
        )
        questions.append(f"Which {from_display} has the most {to_display}s?")

    for ot in object_types:
        props = ot.get("properties", [])
        for p in props:
            if p.get("name") in ("priority", "severity", "risk_level"):
                questions.append(f"Show me all high priority {ot.get('display_name', ot.get('api_name'))}s")
                break
        if len(questions) >= 3:
            break

    if intake:
        processes = intake.get("business_domain", {}).get("key_processes", [])
        if processes:
            questions.append(f"Give me an overview of the {processes[0]} pipeline")

    if len(questions) < 4:
        questions.append(f"How many {object_types[0].get('display_name', 'records')}s are in each status?")

    return questions[:5]
