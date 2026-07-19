"""Microsoft Agent Framework (MAF) chat-client seam.

Centralizes construction of the MAF ``OpenAIChatCompletionClient`` configured for
Azure OpenAI with API-key auth. All LLM traffic in the app routes through this
client so that agents, workflows, and the plain ``llm_client`` helpers share one
configured client and one set of credentials.
"""
from __future__ import annotations

from functools import lru_cache

from agent_framework.openai import OpenAIChatCompletionClient

from ..config import settings


@lru_cache(maxsize=1)
def get_chat_client() -> OpenAIChatCompletionClient:
    """Return a process-wide MAF chat client bound to Azure OpenAI (key auth).

    Passing ``azure_endpoint`` + ``api_key`` routes the client to Azure using
    key-based auth, matching the deployment configured in ``.env``.
    """
    return OpenAIChatCompletionClient(
        model=settings.azure_openai_deployment,
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )
