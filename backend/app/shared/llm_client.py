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


async def llm_call(
    system_prompt: str,
    user_message: str,
    *,
    response_format: dict | None = None,
    temperature: float = 0.3,
) -> str:
    client = get_chat_client()
    options: dict[str, Any] = {"temperature": temperature}
    if response_format:
        options["response_format"] = response_format

    response = await client.get_response(
        [
            Message("system", [system_prompt]),
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
) -> dict:
    raw = await llm_call(
        system_prompt,
        user_message,
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    return json.loads(raw)
