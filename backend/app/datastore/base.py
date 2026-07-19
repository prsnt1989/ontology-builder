from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ColumnSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    sql_type: str
    nullable: bool = True
    primary_key: bool = False
    unique: bool = False
    default: Optional[str] = None
    check_constraint: Optional[str] = None
    foreign_key: Optional[str] = None  # "table.column"


class TableDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table_name: str
    columns: List[ColumnSchema] = Field(default_factory=list)
    indexes: List[str] = Field(default_factory=list)  # CREATE INDEX statements


class TableSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table_name: str
    columns: List[ColumnSchema] = Field(default_factory=list)
    row_count: int = 0


class DataStoreBackend(ABC):
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the backend (create DB file, connect, etc.)."""

    @abstractmethod
    async def create_table(self, table_def: TableDefinition) -> None:
        """Create a table from definition."""

    @abstractmethod
    async def drop_table(self, table_name: str) -> None:
        """Drop a table if it exists."""

    @abstractmethod
    async def execute_ddl(self, ddl: str) -> None:
        """Execute raw DDL (ALTER TABLE, CREATE INDEX, etc.)."""

    @abstractmethod
    async def query(self, sql: str, params: Optional[dict] = None) -> list[dict[str, Any]]:
        """Execute a read-only query and return rows as dicts."""

    @abstractmethod
    async def execute(self, sql: str, params: Optional[dict] = None) -> int:
        """Execute a write statement (INSERT/UPDATE/DELETE). Returns affected row count."""

    @abstractmethod
    async def insert_many(self, table: str, rows: list[dict[str, Any]]) -> int:
        """Insert multiple rows. Returns count inserted."""

    @abstractmethod
    async def get_schema(self, table_name: str) -> Optional[TableSchema]:
        """Get schema info for a table."""

    @abstractmethod
    async def list_tables(self) -> list[str]:
        """List all user tables."""

    @abstractmethod
    async def close(self) -> None:
        """Close connections."""
