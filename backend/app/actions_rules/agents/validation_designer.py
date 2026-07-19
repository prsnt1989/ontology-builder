from __future__ import annotations

import json
from typing import Any

from ...shared.llm_client import llm_json_call
from ..prompt import VALIDATION_DESIGNER_PROMPT


async def run(context: dict[str, Any]) -> dict[str, Any]:
    """Generate validation rules for object types."""
    user_msg = (
        f"Object Types with properties:\n{json.dumps(context['object_types'], indent=2)}\n\n"
        f"Data quality concerns:\n{json.dumps(context.get('data_quality', []), indent=2)}"
    )
    return await llm_json_call(VALIDATION_DESIGNER_PROMPT, user_msg, skill_phase="actions_rules")
