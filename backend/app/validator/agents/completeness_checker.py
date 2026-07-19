"""Deterministic completeness checker — no LLM hallucinations."""
from __future__ import annotations

from typing import Any


async def run(context: dict[str, Any]) -> dict[str, Any]:
    """Check ontology completeness with deterministic Python logic."""
    object_types = context.get("object_types", [])
    relationships = context.get("relationships", [])
    actions = context.get("actions", [])
    lifecycles = context.get("lifecycles", [])

    issues: list[dict[str, Any]] = []
    ot_names = {ot.get("api_name") for ot in object_types}

    for ot in object_types:
        name = ot.get("api_name", "unknown")
        props = ot.get("properties", [])
        prop_names = {p.get("name") for p in props}

        # Must have at least 3 properties
        if len(props) < 3:
            issues.append({
                "severity": "critical",
                "category": "completeness",
                "component": name,
                "message": f"Object type '{name}' has only {len(props)} properties (minimum 3)",
                "suggestion": f"Add more properties to '{name}'",
            })

        # Must have backing_table
        if not ot.get("backing_table"):
            issues.append({
                "severity": "critical",
                "category": "completeness",
                "component": name,
                "message": f"Object type '{name}' missing backing_table",
                "suggestion": f"Add backing_table to '{name}'",
            })

        # title_property must exist in properties
        title_prop = ot.get("title_property")
        if title_prop and title_prop not in prop_names:
            issues.append({
                "severity": "warning",
                "category": "completeness",
                "component": f"{name}.title_property",
                "message": f"title_property '{title_prop}' not in properties of '{name}'",
                "suggestion": f"Add '{title_prop}' as a property or change title_property",
            })

        # primary_key should reference an existing property
        pk = ot.get("primary_key")
        if pk and pk not in prop_names and pk != "id":
            issues.append({
                "severity": "warning",
                "category": "completeness",
                "component": f"{name}.primary_key",
                "message": f"primary_key '{pk}' not in properties of '{name}'",
                "suggestion": f"Add '{pk}' property or use 'id' as primary_key",
            })

        # Each property should have backing_column with column_name and sql_type
        for prop in props:
            bc = prop.get("backing_column")
            if not bc or not bc.get("column_name") or not bc.get("sql_type"):
                issues.append({
                    "severity": "warning",
                    "category": "completeness",
                    "component": f"{name}.{prop.get('name', '?')}",
                    "message": f"Property '{prop.get('name')}' missing backing_column metadata",
                    "suggestion": "Add backing_column with column_name and sql_type",
                })

    # Relationships must reference valid object types
    for rel in relationships:
        rel_name = rel.get("api_name", "unknown")
        from_type = rel.get("from_object_type", "")
        to_type = rel.get("to_object_type", "")

        if from_type and from_type not in ot_names:
            issues.append({
                "severity": "critical",
                "category": "completeness",
                "component": rel_name,
                "message": f"Relationship '{rel_name}' references non-existent from_object_type '{from_type}'",
                "suggestion": f"Remove relationship or add object type '{from_type}'",
            })
        if to_type and to_type not in ot_names:
            issues.append({
                "severity": "critical",
                "category": "completeness",
                "component": rel_name,
                "message": f"Relationship '{rel_name}' references non-existent to_object_type '{to_type}'",
                "suggestion": f"Remove relationship or add object type '{to_type}'",
            })

        # Relationship completeness: cardinality + backing foreign key must be present.
        if not rel.get("cardinality"):
            issues.append({
                "severity": "warning",
                "category": "relationship_completeness",
                "component": rel_name,
                "message": f"Relationship '{rel_name}' is missing a cardinality",
                "suggestion": "Set cardinality (one_to_one|one_to_many|many_to_one|many_to_many)",
            })
        fk = rel.get("backing_foreign_key")
        if not fk or not all(fk.get(k) for k in ("from_table", "from_column", "to_table", "to_column")):
            issues.append({
                "severity": "warning",
                "category": "relationship_completeness",
                "component": rel_name,
                "message": f"Relationship '{rel_name}' is missing a complete backing_foreign_key",
                "suggestion": "Add backing_foreign_key with from_table/from_column/to_table/to_column",
            })

    # Connectivity: every object type should participate in at least one relationship.
    connected: set[str] = set()
    for rel in relationships:
        ft = rel.get("from_object_type", "")
        tt = rel.get("to_object_type", "")
        if ft in ot_names:
            connected.add(ft)
        if tt in ot_names:
            connected.add(tt)
    # Only flag isolation when there is more than one object type (a lone type can't connect).
    if len(ot_names) > 1:
        for ot in object_types:
            name = ot.get("api_name", "unknown")
            if name and name not in connected:
                issues.append({
                    "severity": "warning",
                    "category": "connectivity",
                    "component": name,
                    "message": f"Object type '{name}' has no relationships (isolated in the graph)",
                    "suggestion": f"Add a relationship connecting '{name}' to a related object type, or remove it",
                })

    # Actions must reference valid object types
    for action in actions:
        action_name = action.get("api_name", "unknown")
        action_ot = action.get("object_type", "")
        if action_ot and action_ot not in ot_names:
            issues.append({
                "severity": "critical",
                "category": "completeness",
                "component": action_name,
                "message": f"Action '{action_name}' references non-existent object_type '{action_ot}'",
                "suggestion": f"Remove action or fix object_type reference",
            })

    # Lifecycles must reference valid object types
    for lc in lifecycles:
        lc_ot = lc.get("object_type", "")
        if lc_ot and lc_ot not in ot_names:
            issues.append({
                "severity": "critical",
                "category": "completeness",
                "component": f"Lifecycle:{lc_ot}",
                "message": f"Lifecycle references non-existent object type '{lc_ot}'",
                "suggestion": f"Remove lifecycle or add object type '{lc_ot}'",
            })

    return {"issues": issues}
