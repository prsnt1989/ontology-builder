from __future__ import annotations

import aiosqlite
from pathlib import Path
from typing import Any, Optional

from .base import DataStoreBackend, TableDefinition, TableSchema, ColumnSchema


class SQLiteBackend(DataStoreBackend):
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA foreign_keys = ON")
        # DELETE (rollback) journal, not WAL: WAL relies on shared-memory mmap that
        # SMB/CIFS (Azure Files) doesn't support reliably. The DB lives on a mounted
        # Azure Files share in Azure, and the backend runs as a single replica.
        await self._db.execute("PRAGMA journal_mode = DELETE")
        await self._db.commit()

    async def _get_db(self) -> aiosqlite.Connection:
        if self._db is None:
            await self.initialize()
        return self._db  # type: ignore

    async def create_table(self, table_def: TableDefinition) -> None:
        db = await self._get_db()
        col_defs = []
        for col in table_def.columns:
            parts = [f'"{col.name}" {col.sql_type}']
            if col.primary_key:
                parts.append("PRIMARY KEY")
            if not col.nullable and not col.primary_key:
                parts.append("NOT NULL")
            if col.unique:
                parts.append("UNIQUE")
            if col.default is not None:
                parts.append(f"DEFAULT {col.default}")
            if col.check_constraint:
                parts.append(f"CHECK ({col.check_constraint})")
            if col.foreign_key:
                ref_table, ref_col = col.foreign_key.split(".")
                parts.append(f'REFERENCES "{ref_table}"("{ref_col}")')
            col_defs.append(" ".join(parts))

        ddl = f'CREATE TABLE IF NOT EXISTS "{table_def.table_name}" (\n  '
        ddl += ",\n  ".join(col_defs)
        ddl += "\n)"

        await db.execute(ddl)

        for idx_sql in table_def.indexes:
            await db.execute(idx_sql)

        await db.commit()

    async def drop_table(self, table_name: str) -> None:
        db = await self._get_db()
        await db.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        await db.commit()

    async def execute_ddl(self, ddl: str) -> None:
        db = await self._get_db()
        await db.executescript(ddl)
        await db.commit()

    async def query(self, sql: str, params: Optional[dict] = None) -> list[dict[str, Any]]:
        db = await self._get_db()
        if params:
            cursor = await db.execute(sql, params)
        else:
            cursor = await db.execute(sql)
        rows = await cursor.fetchall()
        if not rows:
            return []
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    async def execute(self, sql: str, params: Optional[dict] = None) -> int:
        db = await self._get_db()
        if params:
            cursor = await db.execute(sql, params)
        else:
            cursor = await db.execute(sql)
        await db.commit()
        return cursor.rowcount

    async def insert_many(self, table: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        db = await self._get_db()
        columns = list(rows[0].keys())
        placeholders = ", ".join(["?" for _ in columns])
        col_names = ", ".join([f'"{c}"' for c in columns])
        sql = f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders})'
        values = [tuple(row.get(c) for c in columns) for row in rows]
        await db.executemany(sql, values)
        await db.commit()
        return len(rows)

    async def get_schema(self, table_name: str) -> Optional[TableSchema]:
        db = await self._get_db()
        cursor = await db.execute(f'PRAGMA table_info("{table_name}")')
        rows = await cursor.fetchall()
        if not rows:
            return None

        # Get foreign key info
        fk_cursor = await db.execute(f'PRAGMA foreign_key_list("{table_name}")')
        fk_rows = await fk_cursor.fetchall()
        fk_map: dict[str, str] = {}
        for fk_row in fk_rows:
            from_col = fk_row[3]
            to_table = fk_row[2]
            to_col = fk_row[4]
            fk_map[from_col] = f"{to_table}.{to_col}"

        columns = []
        for row in rows:
            col_name = row[1]
            columns.append(ColumnSchema(
                name=col_name,
                sql_type=row[2] or "TEXT",
                nullable=not row[3],
                primary_key=bool(row[5]),
                default=row[4],
                foreign_key=fk_map.get(col_name),
            ))

        count_cursor = await db.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        count_row = await count_cursor.fetchone()
        row_count = count_row[0] if count_row else 0

        return TableSchema(table_name=table_name, columns=columns, row_count=row_count)

    async def list_tables(self) -> list[str]:
        db = await self._get_db()
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE '\\_%' ESCAPE '\\' "
            "AND name != 'sqlite_sequence' "
            "ORDER BY name"
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None
