from __future__ import annotations

import json
import logging
from typing import Any

from ..shared.llm_client import llm_json_call
from .base import DataStoreBackend, TableDefinition

logger = logging.getLogger(__name__)

SEED_SYSTEM_PROMPT = """You are a synthetic data generator for an ontology-backed database.

Given a set of table definitions (with column names, types, constraints, and foreign key relationships), generate realistic sample data.

RULES:
1. Generate 15-25 rows per table
2. Respect ALL foreign key constraints — referenced IDs must exist in the already-seeded parent tables (provided below)
3. Respect CHECK constraints (enum values, ranges)
4. Generate realistic, diverse data (names, dates, descriptions should look real)
5. Dates should be in ISO-8601 format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
6. For lifecycle/state columns, distribute records across different states
7. IDs should be sequential integers starting from 1
8. Text fields should have meaningful content, not lorem ipsum

OUTPUT FORMAT:
Return a JSON object where keys are table names and values are arrays of row objects.

Example:
{
  "equipment": [
    {"id": 1, "name": "CNC Machine A", "serial_number": "EQ-000001-MC", "status": "operational"},
    ...
  ],
  "work_orders": [
    {"id": 1, "title": "Routine maintenance for CNC Machine A", "equipment_id": 1, "priority": "medium", "state": "open"},
    ...
  ]
}
"""


def _batch_tables(table_defs: list[TableDefinition], batch_size: int = 4) -> list[list[TableDefinition]]:
    """Split tables into batches respecting FK ordering (already sorted)."""
    batches = []
    for i in range(0, len(table_defs), batch_size):
        batches.append(table_defs[i:i + batch_size])
    return batches


def _describe_tables(table_defs: list[TableDefinition]) -> str:
    """Build human-readable table descriptions for the LLM."""
    parts = []
    for td in table_defs:
        cols = []
        for col in td.columns:
            col_desc = f"  - {col.name} ({col.sql_type})"
            if col.primary_key:
                col_desc += " [PK, auto-increment]"
            if not col.nullable:
                col_desc += " [NOT NULL]"
            if col.check_constraint:
                col_desc += f" [CHECK: {col.check_constraint}]"
            if col.foreign_key:
                col_desc += f" [FK → {col.foreign_key}]"
            cols.append(col_desc)
        parts.append(f"Table: {td.table_name}\n" + "\n".join(cols))
    return "\n\n".join(parts)


async def generate_seed_data(
    table_defs: list[TableDefinition],
    context: str = "",
) -> dict[str, list[dict[str, Any]]]:
    """Use LLM to generate synthetic data in batches."""
    batches = _batch_tables(table_defs, batch_size=4)
    all_data: dict[str, list[dict[str, Any]]] = {}
    seeded_ids: dict[str, list[int]] = {}

    for batch_idx, batch in enumerate(batches):
        tables_desc = _describe_tables(batch)

        # Build FK context: tell LLM what IDs exist in already-seeded tables
        fk_context = ""
        for td in batch:
            for col in td.columns:
                if col.foreign_key:
                    ref_table = col.foreign_key.split(".")[0]
                    if ref_table in seeded_ids:
                        fk_context += f"\nExisting {ref_table} IDs: {seeded_ids[ref_table][:25]}"

        user_msg = f"Generate synthetic data for these tables:\n\n{tables_desc}"
        if fk_context:
            user_msg += f"\n\nALREADY SEEDED (use these IDs for FK references):{fk_context}"
        if context:
            user_msg += f"\n\nBusiness context: {context}"

        logger.info("Seed batch %d/%d: generating data for %s", batch_idx + 1, len(batches),
                    [td.table_name for td in batch])

        try:
            result = await llm_json_call(SEED_SYSTEM_PROMPT, user_msg, temperature=0.7)

            for td in batch:
                rows = result.get(td.table_name, [])
                if rows:
                    all_data[td.table_name] = rows
                    ids = [r.get("id", i + 1) for i, r in enumerate(rows)]
                    seeded_ids[td.table_name] = ids
                    logger.info("  %s: %d rows generated", td.table_name, len(rows))
                else:
                    logger.warning("  %s: no rows in LLM response", td.table_name)
        except Exception as e:
            logger.error("Seed batch %d failed: %s", batch_idx + 1, e)

    return all_data


async def seed_database(
    backend: DataStoreBackend,
    table_defs: list[TableDefinition],
    context: str = "",
) -> dict[str, int]:
    """Generate and insert synthetic data. Returns {table: rows_inserted}."""
    seed_data = await generate_seed_data(table_defs, context)
    counts = {}

    for td in table_defs:
        rows = seed_data.get(td.table_name, [])
        if rows:
            clean_rows = []
            for row in rows:
                row.pop("id", None)
                clean_rows.append(row)
            try:
                inserted = await backend.insert_many(td.table_name, clean_rows)
                counts[td.table_name] = inserted
            except Exception as e:
                logger.warning("Failed to insert rows into %s: %s", td.table_name, e)
                counts[td.table_name] = 0

    total = sum(counts.values())
    logger.info("Seeding complete: %d total rows across %d tables", total, len(counts))
    return counts
