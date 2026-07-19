"""Q&A query planner — a skills-enabled MAF Agent (progressive disclosure).

Unlike the other specialists (which inject skill guidance into a JSON-mode prompt),
the Q&A planner is a real MAF ``Agent`` with the ``SkillsProvider`` attached, so the
model can call the ``load_skill`` tool to pull in the ``nl-to-sql`` skill on demand.
This is the reference implementation for true agent-side skill use.

If the Agent path errors for any reason, we fall back to the original direct
``llm_json_call`` planner so Q&A never breaks.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from agent_framework import Agent, ToolApprovalMiddleware, SkillsProvider

from ...shared.llm_client import llm_json_call
from ...shared.maf_client import get_chat_client
from ...skills import build_skills_provider
from ..prompt import QA_QUERY_PLANNER_PROMPT

logger = logging.getLogger(__name__)

_AGENT_INSTRUCTIONS = (
    QA_QUERY_PLANNER_PROMPT
    + "\n\nA `nl-to-sql` skill is available with detailed SQL-generation rules; "
    "load it with the load_skill tool when you need the full guidance. "
    "Always return ONLY the JSON object described above as your final message."
)


def _extract_json(text: str) -> dict[str, Any]:
    """Pull the JSON object out of the agent's final text response."""
    text = (text or "").strip()
    # Strip markdown code fences if present.
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    # Otherwise take the outermost {...}.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("No JSON object in agent response")


async def _run_with_agent(context: dict[str, Any], user_msg: str) -> dict[str, Any]:
    provider = build_skills_provider()
    context_providers = [provider] if provider is not None else None
    middleware = (
        [ToolApprovalMiddleware(auto_approval_rules=[SkillsProvider.read_only_tools_auto_approval_rule])]
        if provider is not None
        else None
    )
    async with Agent(
        client=get_chat_client(),
        instructions=_AGENT_INSTRUCTIONS,
        context_providers=context_providers,
        middleware=middleware,
    ) as agent:
        session = agent.create_session()
        response = await agent.run(user_msg, session=session)
        return _extract_json(response.text)


async def run(context: dict[str, Any]) -> dict[str, Any]:
    """Translate a natural language question into SQL using actual DB schema.

    Primary path: a skills-enabled MAF Agent that can load the `nl-to-sql` skill.
    Fallback: the direct JSON-mode planner (kept so Q&A is never broken).
    """
    schema_text = context.get("db_schema", "")
    user_msg = f"Database Schema:\n{schema_text}\n\nUser question: {context['question']}"

    try:
        return await _run_with_agent(context, user_msg)
    except Exception as e:  # noqa: BLE001
        logger.warning("Skills-enabled Q&A agent failed (%s); falling back to direct planner.", e)
        return await llm_json_call(QA_QUERY_PLANNER_PROMPT, user_msg, skill_phase="qa")
