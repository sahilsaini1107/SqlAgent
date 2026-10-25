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
    return GeminiLLMClient(
        api_key=settings.gemini_api_key,
        model=model,
        timeout_s=settings.llm_timeout_s,
        max_retries=settings.llm_max_retries,
        max_output_tokens=settings.llm_max_output_tokens,
    )


def default_router() -> ModelRouter:
    # Per-node tiering. Nodes absent from ``overrides`` fall through to the Flash-Lite default
    # (classify, explain) — the high-volume, latency-sensitive path. Core SQL work runs on the
    # stronger Flash tier. Pro stays opt-in; map a node to ``gemini_model_pro`` here to use it.
    core = settings.gemini_model_core
    overrides = {
        "generate": core,
        "repair": core,
        "optimize": core,
    }
    return ModelRouter(default_model=settings.gemini_model, overrides=overrides)


def default_client_for() -> Callable[[str], LLMClient]:
    router = default_router()

    def client_for(node: str) -> LLMClient:
        return _client_for_model(router.model_for(node))

    return client_for
