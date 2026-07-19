"""Shared surgical patch-op engine for ontology mutation.

An LLM plans a minimal set of patch operations; this module applies them
programmatically to the in-memory ``ontology_design`` and ``actions_rules`` dicts.
Used by both the validator's repair agent (fixing validation issues) and the
update-design agent (applying user-requested changes to an existing ontology).

All ops mutate the passed dicts in place and return the number applied.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Documented operation vocabulary, shared by the repair planner and update planner
# prompts so both stay in sync.
PATCH_OPS_REFERENCE = """AVAILABLE OPERATIONS:
- {"op": "remove_relationship", "target": "<api_name>"}
- {"op": "remove_action", "target": "<api_name>"}
- {"op": "remove_actions_for_type", "target": "<object_type_name>"}
- {"op": "remove_permissions_for_type", "target": "<object_type_name>"}
- {"op": "remove_lifecycle", "target": "<object_type_name>"}
- {"op": "remove_object_type", "target": "<api_name>"}
- {"op": "rename_relationship", "target": "<current_api_name>", "new_name": "<new_api_name>"}
- {"op": "update_relationship_field", "target": "<api_name>", "field": "<field_name>", "value": <new_value>}
- {"op": "update_object_type_field", "target": "<api_name>", "field": "<field_name>", "value": <new_value>}
- {"op": "update_action_field", "target": "<api_name>", "field": "<field_name>", "value": <new_value>}
- {"op": "remove_property", "target": "<object_type_api_name>", "property_name": "<name>"}
- {"op": "add_property", "target": "<object_type_api_name>", "property": {"name": "...", "display_name": "...", "type": "string", "required": false, "backing_column": {"column_name": "...", "sql_type": "VARCHAR(255)", "nullable": true}}}
- {"op": "add_object_type", "object_type": {<full object type definition with properties and backing_table>}}
- {"op": "add_relationship", "relationship": {<full relationship: api_name, display_name, from_object_type, to_object_type, cardinality, ...>}}
- {"op": "add_action", "action": {<full action definition>}}
- {"op": "add_permission", "permission": {<full permission rule>}}
- {"op": "add_validation_rule", "validation_rule": {<full validation rule>}}
- {"op": "update_lifecycle_state", "target": "<object_type>", "state": "<state_name>", "field": "<field>", "value": <value>}
- {"op": "update_precondition", "target": "<action_api_name>", "old_value": "<wrong_state>", "new_value": "<correct_state>"}
- {"op": "replace_lifecycle", "target": "<object_type>", "lifecycle": {<complete replacement lifecycle>}}"""


def apply_patches(
    ontology: dict[str, Any],
    actions_rules: dict[str, Any],
    patches: list[dict[str, Any]],
) -> int:
    """Apply patch ops in place to ontology + actions_rules. Returns count applied."""
    applied = 0
    for patch in patches:
        op = patch.get("op", "")
        target = patch.get("target", "")

        try:
            if op == "remove_relationship":
                before = len(ontology.get("relationships", []))
                ontology["relationships"] = [
                    r for r in ontology.get("relationships", []) if r.get("api_name") != target
                ]
                if len(ontology["relationships"]) < before:
                    applied += 1

            elif op == "remove_action":
                before = len(actions_rules.get("actions", []))
                actions_rules["actions"] = [
                    a for a in actions_rules.get("actions", []) if a.get("api_name") != target
                ]
                if len(actions_rules["actions"]) < before:
                    applied += 1

            elif op == "remove_actions_for_type":
                before = len(actions_rules.get("actions", []))
                actions_rules["actions"] = [
                    a for a in actions_rules.get("actions", []) if a.get("object_type") != target
                ]
                if len(actions_rules["actions"]) < before:
                    applied += 1

            elif op == "remove_permissions_for_type":
                before = len(actions_rules.get("permissions", []))
                actions_rules["permissions"] = [
                    p for p in actions_rules.get("permissions", []) if p.get("object_type") != target
                ]
                if len(actions_rules["permissions"]) < before:
                    applied += 1

            elif op == "remove_lifecycle":
                before = len(actions_rules.get("lifecycles", []))
                actions_rules["lifecycles"] = [
                    lc for lc in actions_rules.get("lifecycles", []) if lc.get("object_type") != target
                ]
                if len(actions_rules["lifecycles"]) < before:
                    applied += 1

            elif op == "remove_object_type":
                before = len(ontology.get("object_types", []))
                ontology["object_types"] = [
                    ot for ot in ontology.get("object_types", []) if ot.get("api_name") != target
                ]
                if len(ontology["object_types"]) < before:
                    applied += 1
                    # Cascade: drop dangling relationships/actions/permissions/lifecycles
                    # that referenced the removed type, so no orphaned references remain.
                    ontology["relationships"] = [
                        r
                        for r in ontology.get("relationships", [])
                        if r.get("from_object_type") != target and r.get("to_object_type") != target
                    ]
                    actions_rules["actions"] = [
                        a for a in actions_rules.get("actions", []) if a.get("object_type") != target
                    ]
                    actions_rules["permissions"] = [
                        p for p in actions_rules.get("permissions", []) if p.get("object_type") != target
                    ]
                    actions_rules["lifecycles"] = [
                        lc for lc in actions_rules.get("lifecycles", []) if lc.get("object_type") != target
                    ]

            elif op == "remove_property":
                prop_name = patch.get("property_name", "")
                for ot in ontology.get("object_types", []):
                    if ot.get("api_name") == target:
                        before = len(ot.get("properties", []))
                        ot["properties"] = [p for p in ot.get("properties", []) if p.get("name") != prop_name]
                        if len(ot["properties"]) < before:
                            applied += 1
                        break

            elif op == "rename_relationship":
                new_name = patch.get("new_name", "")
                for r in ontology.get("relationships", []):
                    if r.get("api_name") == target:
                        r["api_name"] = new_name
                        applied += 1
                        break

            elif op == "update_relationship_field":
                field = patch.get("field", "")
                value = patch.get("value")
                for r in ontology.get("relationships", []):
                    if r.get("api_name") == target:
                        r[field] = value
                        applied += 1
                        break

            elif op == "update_object_type_field":
                field = patch.get("field", "")
                value = patch.get("value")
                for ot in ontology.get("object_types", []):
                    if ot.get("api_name") == target:
                        ot[field] = value
                        applied += 1
                        break

            elif op == "update_action_field":
                field = patch.get("field", "")
                value = patch.get("value")
                for a in actions_rules.get("actions", []):
                    if a.get("api_name") == target:
                        a[field] = value
                        applied += 1
                        break

            elif op == "add_property":
                prop = patch.get("property", {})
                for ot in ontology.get("object_types", []):
                    if ot.get("api_name") == target:
                        ot.setdefault("properties", [])
                        existing_names = {p.get("name") for p in ot["properties"]}
                        if prop.get("name") not in existing_names:
                            ot["properties"].append(prop)
                            applied += 1
                        break

            elif op == "add_object_type":
                new_type = patch.get("object_type", {})
                if new_type.get("api_name"):
                    existing = {ot.get("api_name") for ot in ontology.get("object_types", [])}
                    if new_type["api_name"] not in existing:
                        ontology.setdefault("object_types", []).append(new_type)
                        applied += 1

            elif op == "add_relationship":
                new_rel = patch.get("relationship", {})
                if new_rel.get("api_name"):
                    existing = {r.get("api_name") for r in ontology.get("relationships", [])}
                    if new_rel["api_name"] not in existing:
                        ontology.setdefault("relationships", []).append(new_rel)
                        applied += 1

            elif op == "add_action":
                new_action = patch.get("action", {})
                if new_action.get("api_name"):
                    existing = {a.get("api_name") for a in actions_rules.get("actions", [])}
                    if new_action["api_name"] not in existing:
                        actions_rules.setdefault("actions", []).append(new_action)
                        applied += 1

            elif op == "add_permission":
                new_perm = patch.get("permission", {})
                if new_perm:
                    actions_rules.setdefault("permissions", []).append(new_perm)
                    applied += 1

            elif op == "add_validation_rule":
                new_rule = patch.get("validation_rule", {})
                if new_rule:
                    actions_rules.setdefault("validation_rules", []).append(new_rule)
                    applied += 1

            elif op == "replace_lifecycle":
                new_lc = patch.get("lifecycle", {})
                if new_lc:
                    found = False
                    for i, lc in enumerate(actions_rules.get("lifecycles", [])):
                        if lc.get("object_type") == target:
                            actions_rules["lifecycles"][i] = new_lc
                            if "object_type" not in new_lc:
                                actions_rules["lifecycles"][i]["object_type"] = target
                            found = True
                            applied += 1
                            break
                    if not found:
                        new_lc.setdefault("object_type", target)
                        actions_rules.setdefault("lifecycles", []).append(new_lc)
                        applied += 1

            elif op == "update_lifecycle_state":
                state_name = patch.get("state", "")
                field = patch.get("field", "")
                value = patch.get("value")
                for lc in actions_rules.get("lifecycles", []):
                    if lc.get("object_type") == target:
                        for state in lc.get("states", []):
                            if state.get("name") == state_name:
                                state[field] = value
                                applied += 1
                                break
                        break

            elif op == "update_precondition":
                old_val = patch.get("old_value", "")
                new_val = patch.get("new_value", "")
                for a in actions_rules.get("actions", []):
                    if a.get("api_name") == target:
                        preconds = a.get("preconditions", [])
                        a["preconditions"] = [
                            p.replace(old_val, new_val) if isinstance(p, str) else p for p in preconds
                        ]
                        applied += 1
                        break

            else:
                logger.warning("Unknown patch op: %s", op)

        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to apply patch %s on %s: %s", op, target, e)

    logger.info("Applied %d/%d patches successfully.", applied, len(patches))
    return applied
