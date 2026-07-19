from __future__ import annotations

import json
from typing import Any

from ...shared.llm_client import llm_json_call
from ..prompt import DOMAIN_SYNTHESIZER_PROMPT


async def run(context: dict[str, Any]) -> dict[str, Any]:
    """Synthesize search results into structured domain knowledge."""
    user_msg = (
        f"Company intake:\n{json.dumps(context['intake'], indent=2)}\n\n"
        f"Search results:\n{json.dumps(context.get('search_results', []), indent=2)}"
    )
    return await llm_json_call(DOMAIN_SYNTHESIZER_PROMPT, user_msg)
