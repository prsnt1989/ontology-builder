"""Deterministic consistency checker — no LLM hallucinations."""
from __future__ import annotations

from typing import Any


async def run(context: dict[str, Any]) -> dict[str, Any]:
    """Check ontology consistency with deterministic Python logic."""
    object_types = context.get("object_types", [])
    relationships = context.get("relationships", [])
    actions = context.get("actions", [])
    permissions = context.get("permissions", [])

    issues: list[dict[str, Any]] = []
    strengths: list[str] = []

    ot_names = {ot.get("api_name") for ot in object_types}
    rel_names = {r.get("api_name") for r in relationships}
    action_names = {a.get("api_name") for a in actions}

    # Check for duplicate api_names in object types
    seen_ot = set()
    for ot in object_types:
        name = ot.get("api_name", "")
        if name in seen_ot:
            issues.append({
                "severity": "critical",
                "category": "consistency",
                "component": name,
                "message": f"Duplicate object type api_name '{name}'",
                "suggestion": "Rename one of the duplicates",
            })
        seen_ot.add(name)

    # Check for duplicate api_names in relationships
    seen_rel = set()
    for r in relationships:
        name = r.get("api_name", "")
        if name in seen_rel:
            issues.append({
                "severity": "critical",
                "category": "consistency",
                "component": name,
                "message": f"Duplicate relationship api_name '{name}'",
                "suggestion": "Rename one of the duplicates",
            })
        seen_rel.add(name)

    # Check for duplicate api_names in actions
    seen_action = set()
    for a in actions:
        name = a.get("api_name", "")
        if name in seen_action:
            issues.append({
                "severity": "warning",
                "category": "consistency",
                "component": name,
                "message": f"Duplicate action api_name '{name}'",
                "suggestion": "Rename one of the duplicates",
            })
        seen_action.add(name)

    # Permission actions must reference existing actions (or standard 'view'/'read')
    allowed_action_refs = action_names | {"view", "read", "create", "update", "delete"}
    for perm in permissions:
        role = perm.get("role", "?")
        perm_ot = perm.get("object_type", "?")
        for allowed in perm.get("allowed_actions", []):
            if allowed not in allowed_action_refs:
                issues.append({
                    "severity": "warning",
                    "category": "consistency",
                    "component": f"Permission:{role}/{perm_ot}",
                    "message": f"Permission references action '{allowed}' which doesn't exist",
                    "suggestion": f"Add action '{allowed}' or remove from permissions",
                })

    # Naming convention checks (non-blocking)
    for ot in object_types:
        name = ot.get("api_name", "")
        if name and not name[0].isupper():
            issues.append({
                "severity": "warning",
                "category": "consistency",
                "component": name,
                "message": f"Object type '{name}' should be PascalCase",
                "suggestion": f"Rename to '{name[0].upper() + name[1:]}'",
            })

    # Strengths
    if not any(i.get("severity") == "critical" for i in issues):
        strengths.append("No critical consistency issues found")
    if len(ot_names) >= 5:
        strengths.append(f"Good coverage with {len(ot_names)} object types")
    if len(relationships) >= 3:
        strengths.append(f"Well-connected model with {len(relationships)} relationships")

    return {"issues": issues, "strengths": strengths}
