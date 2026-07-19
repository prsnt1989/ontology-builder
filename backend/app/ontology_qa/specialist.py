from __future__ import annotations

from typing import Any

from ..session_store import session_store
from ..datastore.base import DataStoreBackend
from .agents import query_planner, answer_formatter


class OntologyQASpecialist:
    def __init__(self, datastore: DataStoreBackend) -> None:
        self._datastore = datastore

    async def _build_db_schema(self) -> str:
        """Build a compact text representation of the actual database schema."""
        tables = await self._datastore.list_tables()
        parts = []
        for table_name in tables:
            schema = await self._datastore.get_schema(table_name)
            if not schema:
                continue
            cols = []
            for col in schema.columns:
                col_str = f"{col.name} ({col.sql_type})"
                extras = []
                if col.primary_key:
                    extras.append("PK")
                if not col.nullable:
                    extras.append("NOT NULL")
                if col.foreign_key:
                    extras.append(f"FK → {col.foreign_key}")
                if extras:
                    col_str += f" [{', '.join(extras)}]"
                cols.append(col_str)
            parts.append(f"Table: {table_name} ({schema.row_count} rows)\n  Columns: {', '.join(cols)}")
        return "\n".join(parts)

    async def ask(self, session_id: str, question: str) -> dict[str, Any]:
        """Answer a natural language question using ontology + data."""
        ontology = session_store.get_value(session_id, "ontology_design")
        if not ontology:
            return {
                "type": "error",
                "response": "No ontology found for this session. Generate an ontology first.",
            }

        # Step 1: Build actual DB schema and plan the SQL query
        db_schema = await self._build_db_schema()
        if not db_schema:
            return {
                "type": "error",
                "response": "No database tables found. Please generate the ontology and seed data first.",
            }
        plan = await query_planner.run({
            "db_schema": db_schema,
            "question": question,
        })
        sql = plan.get("sql", "")

        if not sql:
            return {
                "type": "error",
                "response": "Could not generate a valid query for your question.",
                "explanation": plan.get("explanation", ""),
            }

        # Step 2: Execute the query
        try:
            rows = await self._datastore.query(sql)
        except Exception as e:
            return {
                "type": "error",
                "response": f"Query execution failed: {str(e)}",
                "sql": sql,
                "explanation": plan.get("explanation", ""),
            }

        # Step 3: Format the answer (with business context for better follow-ups)
        intake = session_store.get_value(session_id, "intake_output")
        business_context = ""
        if intake:
            industry = intake.get("company_profile", {}).get("industry", "")
            domain = intake.get("business_domain", {}).get("department", "")
            goals = intake.get("problem_statement", {}).get("goals", [])
            processes = intake.get("business_domain", {}).get("key_processes", [])
            business_context = f"Industry: {industry}. Domain: {domain}. Goals: {', '.join(goals) if goals else 'N/A'}. Key processes: {', '.join(processes) if processes else 'N/A'}."

        formatted = await answer_formatter.run({
            "question": question,
            "sql": sql,
            "rows": rows,
            "ontology": ontology,
            "business_context": business_context,
        })

        return {
            "type": "qa_response",
            "response": formatted.get("answer", "No answer could be generated."),
            "sql": sql,
            "explanation": plan.get("explanation", ""),
            "object_types_used": plan.get("object_types_used", []),
            "properties_used": plan.get("properties_used", []),
            "assumptions": plan.get("assumptions", []),
            "summary_table": formatted.get("summary_table"),
            "insights": formatted.get("insights", []),
            "follow_up_questions": formatted.get("follow_up_questions", []),
            "row_count": len(rows),
        }
