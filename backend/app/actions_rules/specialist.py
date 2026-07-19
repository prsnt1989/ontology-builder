from __future__ import annotations

import json
from typing import Any

from ..session_store import session_store
from .agents import action_designer, permission_designer, validation_designer, lifecycle_designer
from .lifecycle_fixer import fix_lifecycles


class ActionsRulesSpecialist:
    async def analyze(self, session_id: str) -> dict[str, Any]:
        """Orchestrate the 4 sub-agents to generate actions, permissions, rules, lifecycles."""
        intake = session_store.get_value(session_id, "intake_output")
        ontology = session_store.get_value(session_id, "ontology_design")

        if not intake or not ontology:
            return {"type": "error", "response": "Missing intake or ontology design data."}

        object_types = ontology.get("object_types", [])
        workflows = intake.get("workflows", {})
        user_roles = intake.get("user_roles", [])
        data_quality = intake.get("data_sources", [{}])[0].get("quality_issues", []) if intake.get("data_sources") else []
        key_processes = intake.get("business_domain", {}).get("key_processes", [])

        # Step 1: Design actions
        actions_result = await action_designer.run({
            "object_types": object_types,
            "workflows": workflows,
        })
        actions = actions_result.get("actions", [])

        # Step 2: Design permissions (needs actions list)
        permissions_result = await permission_designer.run({
            "object_types": object_types,
            "user_roles": user_roles,
            "actions": actions,
        })
        permissions = permissions_result.get("permissions", [])

        # Step 3: Design validation rules
        validation_result = await validation_designer.run({
            "object_types": object_types,
            "data_quality": data_quality,
        })
        validation_rules = validation_result.get("validation_rules", [])

        # Step 4: Design lifecycles
        lifecycle_result = await lifecycle_designer.run({
            "object_types": object_types,
            "workflows": workflows,
            "key_processes": key_processes,
        })
        lifecycles = lifecycle_result.get("lifecycles", [])
        lifecycles = fix_lifecycles(lifecycles)

        # Merge all results
        output = {
            "actions": actions,
            "permissions": permissions,
            "validation_rules": validation_rules,
            "lifecycles": lifecycles,
        }

        session_store.update(session_id, "actions_rules", output)
        session_store.update(session_id, "phase", "validation")

        return {
            "type": "actions_rules_complete",
            "response": (
                f"Generated {len(actions)} actions, "
                f"{len(permissions)} permission rules, "
                f"{len(validation_rules)} validation rules, and "
                f"{len(lifecycles)} lifecycle definitions."
            ),
            "output": output,
            "complete": True,
        }
