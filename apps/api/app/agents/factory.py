"""Wire the configured provider/model into the graph's client-selection seam.

``default_client_for`` returns a callable mapping a node name to an ``LLMClient``. Today every
node resolves to the single configured Gemini model; the ``ModelRouter`` is where per-node
tiers plug in later.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cache

from app.agents.llm import GeminiLLMClient, LLMClient
from app.agents.model_router import ModelRouter
from app.config import settings


@cache
def _client_for_model(model: str) -> GeminiLLMClient:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    return GeminiLLMClient(api_key=settings.gemini_api_key, model=model)


def default_router() -> ModelRouter:
    return ModelRouter(default_model=settings.gemini_model)


def default_client_for() -> Callable[[str], LLMClient]:
    router = default_router()

    def client_for(node: str) -> LLMClient:
        return _client_for_model(router.model_for(node))

    return client_for
