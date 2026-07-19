"""LLM helper functions, routed through the Microsoft Agent Framework client.

These keep their original signatures so every specialist and sub-agent that calls
``llm_call`` / ``llm_json_call`` continues to work unchanged. Under the hood the
call now flows through MAF's ``OpenAIChatCompletionClient`` (Azure OpenAI) instead
of a raw ``AsyncAzureOpenAI`` client, so LLM traffic shares one configured client,
telemetry, and middleware surface with the agents and workflow.
"""
from __future__ import annotations

import json
from typing import Any

from agent_framework import Message

from .maf_client import get_chat_client


def _with_skill(system_prompt: str, skill_phase: str | None) -> str:
    """Prepend the relevant skill's guidance to the system prompt, if any."""
    if not skill_phase:
        return system_prompt
    # Lazy import avoids any import-order concerns; skills.py only imports agent_framework.
    from ..skills import skill_body_for_phase

    body = skill_body_for_phase(skill_phase)
    if not body:
        return system_prompt
    return f"## Design guidance (skill)\n\n{body}\n\n---\n\n{system_prompt}"


async def llm_call(
    system_prompt: str,
    user_message: str,
    *,
    response_format: dict | None = None,
    temperature: float = 0.3,
    skill_phase: str | None = None,
) -> str:
    client = get_chat_client()
    options: dict[str, Any] = {"temperature": temperature}
    if response_format:
        options["response_format"] = response_format

    response = await client.get_response(
        [
            Message("system", [_with_skill(system_prompt, skill_phase)]),
            Message("user", [user_message]),
        ],
        options=options,
    )
    return response.text or ""


async def llm_json_call(
    system_prompt: str,
    user_message: str,
    *,
    temperature: float = 0.3,
    skill_phase: str | None = None,
) -> dict:
    raw = await llm_call(
        system_prompt,
        user_message,
        response_format={"type": "json_object"},
        temperature=temperature,
        skill_phase=skill_phase,
    )
    return json.loads(raw)
