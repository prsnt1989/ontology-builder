from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from .base import DataStoreBackend, TableDefinition, ColumnSchema


MIGRATIONS_TABLE = "_ontology_migrations"

MIGRATIONS_DDL = f"""
CREATE TABLE IF NOT EXISTS "{MIGRATIONS_TABLE}" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL,
    use_case TEXT,
    applied_at TEXT NOT NULL,
    migration_sql TEXT NOT NULL
);
"""


class MigrationManager:
    def __init__(self, backend: DataStoreBackend) -> None:
        self._backend = backend

    async def initialize(self) -> None:
        await self._backend.execute_ddl(MIGRATIONS_DDL)

    async def get_applied_versions(self) -> list[dict[str, Any]]:
        return await self._backend.query(
            f'SELECT version, use_case, applied_at FROM "{MIGRATIONS_TABLE}" ORDER BY id'
        )

    async def is_version_applied(self, version: str, use_case: Optional[str] = None) -> bool:
        if use_case:
            rows = await self._backend.query(
                f'SELECT 1 FROM "{MIGRATIONS_TABLE}" WHERE version = ? AND use_case = ?',
                (version, use_case),
            )
        else:
            rows = await self._backend.query(
                f'SELECT 1 FROM "{MIGRATIONS_TABLE}" WHERE version = ? AND use_case IS NULL',
                (version,),
            )
        return len(rows) > 0

    async def apply_migration(
        self,
        version: str,
        ddl: str,
        use_case: Optional[str] = None,
    ) -> None:
        await self._backend.execute_ddl(ddl)

        now = datetime.now(timezone.utc).isoformat()
        await self._backend.execute(
            f'INSERT INTO "{MIGRATIONS_TABLE}" (version, use_case, applied_at, migration_sql) '
            f"VALUES (?, ?, ?, ?)",
            (version, use_case, now, ddl),
        )

    async def generate_extension_ddl(
        self,
        new_tables: list[TableDefinition],
        existing_tables: list[str],
    ) -> str:
        """Generate DDL for extension — only CREATE new tables, never ALTER existing."""
        from .schema_generator import generate_ddl

        new_only = [td for td in new_tables if td.table_name not in existing_tables]
        if not new_only:
            return ""
        return generate_ddl(new_only)
