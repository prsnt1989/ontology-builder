"""Bing Web Search MCP Server."""
from __future__ import annotations

import os
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("web-search")

BING_API_KEY = os.environ.get("BING_SEARCH_API_KEY", "")
BING_ENDPOINT = os.environ.get("BING_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search")


@mcp.tool(description="Search the web using Bing Search API. Returns titles, URLs, and snippets.")
async def search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web for information."""
    if not BING_API_KEY:
        return [{"error": "BING_SEARCH_API_KEY not configured"}]

    headers = {"Ocp-Apim-Subscription-Key": BING_API_KEY}
    params = {"q": query, "count": max_results, "responseFilter": "Webpages"}

    async with httpx.AsyncClient() as client:
        response = await client.get(BING_ENDPOINT, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

    results = []
    for page in data.get("webPages", {}).get("value", []):
        results.append({
            "title": page.get("name", ""),
            "url": page.get("url", ""),
            "snippet": page.get("snippet", ""),
        })
    return results


@mcp.tool(description="Fetch the text content of a web page.")
async def fetch_page(url: str) -> str:
    """Fetch and return the text content of a URL."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        response = await client.get(url)
        response.raise_for_status()
    # Return first 5000 chars to avoid token overflow
    return response.text[:5000]


app = mcp.streamable_http_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8030)
