from __future__ import annotations

import json
from typing import Any

from ...shared.llm_client import llm_json_call
from ..prompt import LIFECYCLE_DESIGNER_PROMPT


async def run(context: dict[str, Any]) -> dict[str, Any]:
    """Generate lifecycle state machines for applicable object types."""
    user_msg = (
        f"Object Types:\n{json.dumps(context['object_types'], indent=2)}\n\n"
        f"Workflow complexity:\n{json.dumps(context.get('workflows', {}), indent=2)}\n\n"
        f"Key processes:\n{json.dumps(context.get('key_processes', []), indent=2)}"
    )
    return await llm_json_call(LIFECYCLE_DESIGNER_PROMPT, user_msg, skill_phase="actions_rules")
