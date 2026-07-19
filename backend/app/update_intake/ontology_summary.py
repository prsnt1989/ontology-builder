"""Compact textual summary of an existing ontology for LLM prompts."""
from __future__ import annotations

import json
from typing import Any


def summarize_ontology(ontology_design: dict[str, Any], actions_rules: dict[str, Any] | None = None) -> str:
    """Produce a compact, token-efficient summary of the current ontology."""
    ontology_design = ontology_design or {}
    actions_rules = actions_rules or {}

    lines: list[str] = []
    lines.append("OBJECT TYPES:")
    for ot in ontology_design.get("object_types", []):
        props = ot.get("properties", [])
        prop_str = ", ".join(
            f"{p.get('name')}:{p.get('type', '?')}" for p in props[:20]
        )
        lines.append(f"- {ot.get('api_name')} ({ot.get('display_name')}): [{prop_str}]")

    lines.append("\nRELATIONSHIPS:")
    for r in ontology_design.get("relationships", []):
        lines.append(
            f"- {r.get('api_name')}: {r.get('from_object_type')} -> {r.get('to_object_type')} "
            f"({r.get('cardinality')})"
        )

    if actions_rules.get("actions"):
        action_names = [a.get("api_name") for a in actions_rules.get("actions", [])]
        lines.append(f"\nACTIONS: {json.dumps(action_names)}")

    if actions_rules.get("lifecycles"):
        lifecycles = {
            lc.get("object_type"): [s.get("name") for s in lc.get("states", [])]
            for lc in actions_rules.get("lifecycles", [])
        }
        lines.append(f"\nLIFECYCLE STATES PER TYPE: {json.dumps(lifecycles)}")

    return "\n".join(lines)
