from __future__ import annotations

import json
from typing import Any

from ...shared.llm_client import llm_json_call
from ..prompt import ACTION_DESIGNER_PROMPT


async def run(context: dict[str, Any]) -> dict[str, Any]:
    """Generate actions for all object types."""
    user_msg = (
        f"Object Types:\n{json.dumps(context['object_types'], indent=2)}\n\n"
        f"Workflows info:\n{json.dumps(context.get('workflows', {}), indent=2)}"
    )
    return await llm_json_call(ACTION_DESIGNER_PROMPT, user_msg)
