from __future__ import annotations

import json
from typing import Any

from ...shared.llm_client import llm_json_call
from ..prompt import QA_ANSWER_FORMATTER_PROMPT


async def run(context: dict[str, Any]) -> dict[str, Any]:
    """Format raw query results into a human-readable answer."""
    business_ctx = context.get("business_context", "")
    user_msg = (
        f"Original question: {context['question']}\n\n"
        f"SQL executed: {context['sql']}\n\n"
        f"Results ({len(context.get('rows', []))} rows):\n"
        f"{json.dumps(context.get('rows', [])[:50], indent=2)}\n\n"
        f"Ontology context (display names):\n{json.dumps(context['ontology'], indent=2)}"
    )
    if business_ctx:
        user_msg += f"\n\nBusiness context: {business_ctx}"
    return await llm_json_call(QA_ANSWER_FORMATTER_PROMPT, user_msg)
