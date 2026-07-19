from __future__ import annotations

from typing import Any

from ...shared.web_search import web_search


async def run(queries: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Execute web searches for each planned query using Azure OpenAI Responses API."""
    results = []

    for q in queries[:6]:
        try:
            search_results = await web_search(
                q["query"],
                context=q.get("purpose", ""),
            )
            results.append({
                "query": q["query"],
                "purpose": q.get("purpose", ""),
                "results": search_results,
            })
        except Exception:
            results.append({
                "query": q["query"],
                "purpose": q.get("purpose", ""),
                "results": [],
                "error": "Search failed",
            })

    return results
