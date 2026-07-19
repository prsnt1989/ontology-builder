"""Web search via Azure OpenAI Responses API with web_search tool."""
from __future__ import annotations

import asyncio
import json
import re
import logging
from typing import Any

from ..config import settings

logger = logging.getLogger(__name__)


def _do_search(query: str, context: str = "") -> list[dict[str, Any]]:
    """Synchronous web search using Azure OpenAI Responses API."""
    from openai import AzureOpenAI

    prompt = (
        f"Search the web for: {query}\n"
    )
    if context:
        prompt += f"Context: {context}\n"
    prompt += (
        "\nReturn ONLY a JSON array of the top 5 most relevant results:\n"
        '[{"title": "page title", "url": "https://...", "snippet": "relevant excerpt", "relevance": "high|medium"}]\n'
        "Return ONLY valid JSON, no markdown or explanation."
    )

    client = AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version="2025-03-01-preview",
    )

    resp = client.responses.create(
        model=settings.azure_openai_deployment,
        input=prompt,
        tools=[{"type": "web_search", "search_context_size": "medium"}],
        max_output_tokens=2000,
    )

    text = ""
    for item in resp.output:
        if item.type == "message":
            for content in item.content:
                if hasattr(content, "text"):
                    text += content.text

    # Strip citation markers
    text = re.sub(r'citeturn\d+\w*\d*', '', text)

    # Parse JSON array from response
    json_match = re.search(r'\[[\s\S]*\]', text)
    if not json_match:
        logger.warning("No JSON array in web search response for query: %s", query)
        return []

    try:
        results = json.loads(json_match.group())
        return results if isinstance(results, list) else []
    except json.JSONDecodeError as e:
        logger.warning("JSON parse error in web search response: %s", e)
        return []


async def web_search(query: str, context: str = "") -> list[dict[str, Any]]:
    """Execute a web search via Azure OpenAI Responses API (async wrapper)."""
    try:
        return await asyncio.to_thread(_do_search, query, context)
    except Exception as e:
        logger.warning("Web search failed for '%s': %s", query, e)
        return []
