from __future__ import annotations

import json
from typing import Any

from ...shared.llm_client import llm_json_call
from ..prompt import PERMISSION_DESIGNER_PROMPT


async def run(context: dict[str, Any]) -> dict[str, Any]:
    """Generate permission rules from object types and user roles."""
    user_msg = (
        f"Object Types:\n{json.dumps(context['object_types'], indent=2)}\n\n"
        f"User Roles:\n{json.dumps(context.get('user_roles', []), indent=2)}\n\n"
        f"Actions (already defined):\n{json.dumps(context.get('actions', []), indent=2)}"
    )
    return await llm_json_call(PERMISSION_DESIGNER_PROMPT, user_msg, skill_phase="actions_rules")
