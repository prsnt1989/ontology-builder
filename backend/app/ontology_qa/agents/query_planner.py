from __future__ import annotations

import json
from typing import Any

from ...shared.llm_client import llm_json_call
from ..prompt import QA_QUERY_PLANNER_PROMPT


async def run(context: dict[str, Any]) -> dict[str, Any]:
    """Translate a natural language question into SQL using actual DB schema."""
    schema_text = context.get("db_schema", "")

    user_msg = (
        f"Database Schema:\n{schema_text}\n\n"
        f"User question: {context['question']}"
    )
    return await llm_json_call(QA_QUERY_PLANNER_PROMPT, user_msg)
