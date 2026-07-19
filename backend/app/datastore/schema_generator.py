from __future__ import annotations

from typing import Any

from .base import TableDefinition, ColumnSchema


PROPERTY_TYPE_TO_SQL = {
    "string": "TEXT",
    "integer": "INTEGER",
    "float": "REAL",
    "boolean": "INTEGER",
    "date": "TEXT",
    "datetime": "TEXT",
    "timestamp": "TEXT",
    "enum": "TEXT",
    "array": "TEXT",
    "object": "TEXT",
    "geospatial": "TEXT",
    "attachment": "TEXT",
}


def ontology_to_table_definitions(
    object_types: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> list[TableDefinition]:
    """Convert ontology YAML object types + relationships into TableDefinitions."""
    fk_map: dict[str, list[dict]] = {}
    for rel in relationships:
        if rel.get("backing_foreign_key"):
            fk = rel["backing_foreign_key"]
            fk_map.setdefault(fk["from_table"], []).append(fk)

    table_defs = []
    for ot in object_types:
        bt = ot.get("backing_table")
        if not bt:
            continue

        table_name = bt["table_name"]
        pk_col = bt.get("primary_key_column", "id")

        columns: list[ColumnSchema] = []
        columns.append(ColumnSchema(
            name=pk_col,
            sql_type="INTEGER",
            primary_key=True,
            nullable=False,
        ))

        properties = ot.get("properties", [])
        for prop in properties:
            bc = prop.get("backing_column")
            if bc:
                col_name = bc["column_name"]
                sql_type = bc.get("sql_type", PROPERTY_TYPE_TO_SQL.get(prop.get("type", "string"), "TEXT"))
            else:
                col_name = prop["name"]
                sql_type = PROPERTY_TYPE_TO_SQL.get(prop.get("type", "string"), "TEXT")

            if col_name == pk_col:
                continue

            fk_ref = None
            for fk in fk_map.get(table_name, []):
                if fk["from_column"] == col_name:
                    fk_ref = f"{fk['to_table']}.{fk['to_column']}"
                    break

            check = None
            if bc and bc.get("check_constraint"):
                check = bc["check_constraint"]
            elif prop.get("type") == "enum" and prop.get("enum_values"):
                vals = ", ".join([f"'{v}'" for v in prop["enum_values"]])
                check = f'"{col_name}" IN ({vals})'

            columns.append(ColumnSchema(
                name=col_name,
                sql_type=sql_type,
                nullable=not prop.get("required", False),
                unique=prop.get("unique", False),
                check_constraint=check,
                foreign_key=fk_ref,
            ))

        indexes = []
        for prop in properties:
            bc = prop.get("backing_column", {})
            col_name = bc.get("column_name", prop["name"]) if bc else prop["name"]
            if prop.get("indexed") or (bc and bc.get("indexed")):
                idx_name = f"idx_{table_name}_{col_name}"
                indexes.append(
                    f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table_name}"("{col_name}")'
                )

        table_defs.append(TableDefinition(
            table_name=table_name,
            columns=columns,
            indexes=indexes,
        ))

    return _sort_by_dependencies(table_defs)


def _sort_by_dependencies(table_defs: list[TableDefinition]) -> list[TableDefinition]:
    """Topological sort so parent tables are created before children."""
    table_map = {td.table_name: td for td in table_defs}
    visited: set[str] = set()
    result: list[TableDefinition] = []

    def visit(name: str) -> None:
        if name in visited:
            return
        visited.add(name)
        td = table_map.get(name)
        if not td:
            return
        for col in td.columns:
            if col.foreign_key:
                ref_table = col.foreign_key.split(".")[0]
                if ref_table in table_map:
                    visit(ref_table)
        result.append(td)

    for td in table_defs:
        visit(td.table_name)

    return result


def generate_ddl(table_defs: list[TableDefinition]) -> str:
    """Generate complete DDL script from table definitions."""
    statements = []
    for td in table_defs:
        col_defs = []
        for col in td.columns:
            parts = [f'"{col.name}" {col.sql_type}']
            if col.primary_key:
                parts.append("PRIMARY KEY AUTOINCREMENT" if col.sql_type == "INTEGER" else "PRIMARY KEY")
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
            col_defs.append("  " + " ".join(parts))

        ddl = f'CREATE TABLE IF NOT EXISTS "{td.table_name}" (\n'
        ddl += ",\n".join(col_defs)
        ddl += "\n);"
        statements.append(ddl)
        statements.extend([f"{idx};" for idx in td.indexes])

    return "\n\n".join(statements)
