"""Repair agent: LLM plans surgical patches, Python applies them."""
from __future__ import annotations

import json
import logging
from typing import Any

from ...shared.llm_client import llm_json_call
from ...shared.patch_ops import apply_patches

logger = logging.getLogger(__name__)

PLANNER_PROMPT = """You are an Ontology Repair Planner. You analyze validation issues and produce a minimal set of PATCH OPERATIONS to fix them.

You will receive:
1. A list of defined object type api_names (so you know what exists)
2. A list of defined relationship api_names
3. A list of validation issues to fix

DO NOT regenerate the full ontology. Instead, output a JSON object with a "patches" array of surgical operations and a "reasoning" string.

AVAILABLE OPERATIONS:
- {"op": "remove_relationship", "target": "<api_name>"}
- {"op": "remove_action", "target": "<api_name>"}
- {"op": "remove_actions_for_type", "target": "<object_type_name>"}
- {"op": "remove_permissions_for_type", "target": "<object_type_name>"}
- {"op": "remove_lifecycle", "target": "<object_type_name>"}
- {"op": "remove_object_type", "target": "<api_name>"}
- {"op": "rename_relationship", "target": "<current_api_name>", "new_name": "<new_api_name>"}
- {"op": "update_relationship_field", "target": "<api_name>", "field": "<field_name>", "value": <new_value>}
- {"op": "update_action_field", "target": "<api_name>", "field": "<field_name>", "value": <new_value>}
- {"op": "add_property", "target": "<object_type_api_name>", "property": {"name": "...", "display_name": "...", "type": "string", "required": false, "backing_column": {"column_name": "...", "sql_type": "VARCHAR(255)", "nullable": true}}}
- {"op": "add_object_type", "object_type": {<full object type definition with properties>}}
- {"op": "add_relationship", "relationship": {"api_name": "...", "display_name": "...", "description": "...", "from_object_type": "<ApiName>", "to_object_type": "<ApiName>", "cardinality": "many_to_one", "inverse_name": "...", "backing_foreign_key": {"from_table": "...", "from_column": "...", "to_table": "...", "to_column": "id", "on_delete": "RESTRICT"}}}
- {"op": "update_lifecycle_state", "target": "<object_type>", "state": "<state_name>", "field": "<field>", "value": <value>}
- {"op": "update_precondition", "target": "<action_api_name>", "old_value": "<wrong_state>", "new_value": "<correct_state>"}
- {"op": "replace_lifecycle", "target": "<object_type>", "lifecycle": {<complete replacement lifecycle with correct states and transitions>}}

STRATEGY RULES:
1. PREFER REMOVING invalid references over adding missing object types. If something references a non-existent type, remove the referencing items. (EXCEPTION: connectivity issues — see rule 10 — must be fixed by ADDING a relationship, not by removing the object type.)
2. GROUP related issues: if 10 actions all reference invalid type "Foo", one "remove_actions_for_type" fixes all 10.
3. For duplicate api_names: rename the SECOND occurrence (keep the first).
4. For self-referential inverse_names: set inverse_name to the actual inverse relationship's api_name.
5. For polymorphic FK issues (one column → multiple tables): remove the problematic relationships; the semantic connection can remain implicit.
6. NEVER output the full ontology. Only patches.
7. Each patch must fix at least one reported issue. Don't add patches for things not in the issue list.
8. For LIFECYCLE issues (states not matching transitions): use "replace_lifecycle" with a COMPLETE corrected lifecycle. This fixes all state/transition inconsistencies for that type in ONE patch. The states[].name values MUST appear in transitions from_state/to_state and in allowed_transitions.
9. When a lifecycle has many issues (5+ related to one object_type), ALWAYS use replace_lifecycle instead of individual patches.
10. For CONNECTIVITY issues (object type has no relationships / isolated): you MUST fix it with "add_relationship" — connect the isolated type to the most semantically related EXISTING object type, with a proper cardinality and a COMPLETE backing_foreign_key (the FK column lives on the "many" side's table; use the target's primary_key_column, usually "id", as to_column). NEVER use remove_object_type for a connectivity issue — the object type is real business data the user wants; removing it is not an acceptable fix. Emit exactly one add_relationship per isolated type.
11. For RELATIONSHIP_COMPLETENESS issues (missing cardinality or backing_foreign_key): use "update_relationship_field" to set the missing "cardinality" and/or "backing_foreign_key" (a full object with from_table/from_column/to_table/to_column). Do not remove the relationship just because it is incomplete — complete it.

Return JSON:
{
  "patches": [...],
  "reasoning": "1-3 sentence explanation of the repair strategy"
}"""


async def run(context: dict[str, Any]) -> dict[str, Any]:
    """Plan repairs and apply them as patches."""
    ontology = context["ontology_design"]
    actions_rules = context.get("actions_rules", {})
    issues = context["issues"]

    # Object types with their backing table + primary key, so the planner can write
    # correct backing_foreign_key values when adding/completing relationships.
    object_type_summary = [
        {
            "api_name": ot.get("api_name", ""),
            "backing_table": (ot.get("backing_table") or {}).get("table_name", ""),
            "primary_key_column": (ot.get("backing_table") or {}).get("primary_key_column", "id"),
        }
        for ot in ontology.get("object_types", [])
    ]
    # Relationship summaries (name + endpoints + cardinality + whether FK present) so the
    # planner can complete incomplete relationships and avoid duplicating connections.
    relationship_summary = [
        {
            "api_name": r.get("api_name", ""),
            "from": r.get("from_object_type", ""),
            "to": r.get("to_object_type", ""),
            "cardinality": r.get("cardinality", ""),
            "has_backing_foreign_key": bool(r.get("backing_foreign_key")),
        }
        for r in ontology.get("relationships", [])
    ]

    # Provide lifecycle state summaries so the planner can write correct replacements
    lifecycle_summary = {}
    for lc in actions_rules.get("lifecycles", []):
        obj_type = lc.get("object_type", "")
        states = [s.get("name") for s in lc.get("states", []) if s.get("name")]
        lifecycle_summary[obj_type] = states

    user_msg = (
        f"DEFINED OBJECT TYPES (api_name, backing_table, primary_key_column): "
        f"{json.dumps(object_type_summary)}\n\n"
        f"DEFINED RELATIONSHIPS: {json.dumps(relationship_summary)}\n\n"
        f"CURRENT LIFECYCLE STATES PER TYPE: {json.dumps(lifecycle_summary)}\n\n"
        f"VALIDATION ISSUES TO FIX ({len(issues)} total):\n"
        f"{json.dumps(issues, indent=2)}"
    )

    # Step 1: LLM plans the patches
    plan = await llm_json_call(PLANNER_PROMPT, user_msg, skill_phase="validation")
    patches = plan.get("patches", [])
    reasoning = plan.get("reasoning", "")

    logger.info("Repair planner produced %d patches. Reasoning: %s", len(patches), reasoning)

    # Step 2: Apply patches programmatically (shared engine)
    apply_patches(ontology, actions_rules, patches)

    return {
        "ontology_design": ontology,
        "actions_rules": actions_rules,
    }
