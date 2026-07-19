from __future__ import annotations

import json
from typing import Any

from ...shared.llm_client import llm_json_call
from ..prompt import SEARCH_PLANNER_PROMPT


async def run(context: dict[str, Any]) -> dict[str, Any]:
    """Plan search queries based on intake data."""
    user_msg = f"Company intake:\n{json.dumps(context['intake'], indent=2)}"
    return await llm_json_call(SEARCH_PLANNER_PROMPT, user_msg)
