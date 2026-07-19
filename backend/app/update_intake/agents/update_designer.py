"""Update designer: plans surgical patch ops to apply a confirmed change plan."""
from __future__ import annotations

import json
import logging
from typing import Any

from ...shared.llm_client import llm_json_call
from ...shared.patch_ops import apply_patches, PATCH_OPS_REFERENCE
from ..prompt import UPDATE_DESIGN_PROMPT

logger = logging.getLogger(__name__)


async def run(ontology: dict[str, Any], actions_rules: dict[str, Any], update_plan: dict[str, Any]) -> dict[str, Any]:
    """Plan and apply patches for the confirmed changes. Mutates dicts in place."""
    object_types_view = [
        {"api_name": ot.get("api_name"), "properties": [p.get("name") for p in ot.get("properties", [])]}
        for ot in ontology.get("object_types", [])
    ]
    relationship_names = [r.get("api_name") for r in ontology.get("relationships", [])]
    lifecycle_summary = {
        lc.get("object_type"): [s.get("name") for s in lc.get("states", [])]
        for lc in actions_rules.get("lifecycles", [])
    }

    user_msg = (
        f"EXISTING OBJECT TYPES (api_name + property names):\n{json.dumps(object_types_view, indent=2)}\n\n"
        f"EXISTING RELATIONSHIPS: {json.dumps(relationship_names)}\n\n"
        f"EXISTING LIFECYCLE STATES PER TYPE: {json.dumps(lifecycle_summary)}\n\n"
        f"CONFIRMED CHANGE PLAN:\n{json.dumps(update_plan.get('changes', []), indent=2)}"
    )

    prompt = UPDATE_DESIGN_PROMPT % PATCH_OPS_REFERENCE
    try:
        plan = await llm_json_call(prompt, user_msg)
    except Exception as e:  # noqa: BLE001
        logger.warning("Update designer failed: %s", e)
        return {"patches": [], "applied": 0, "reasoning": f"error: {e}"}

    patches = plan.get("patches", [])
    reasoning = plan.get("reasoning", "")
    applied = apply_patches(ontology, actions_rules, patches)
    logger.info("Update designer applied %d/%d patches. Reasoning: %s", applied, len(patches), reasoning)
    return {"patches": patches, "applied": applied, "reasoning": reasoning}
