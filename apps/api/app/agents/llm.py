"""LLM client abstraction.

A small provider-agnostic seam: nodes depend on the ``LLMClient`` protocol, not on a
concrete SDK. The Gemini implementation returns both the validated structured output and the
token/latency usage so the graph can record per-call telemetry. Tests inject a fake client
that satisfies the same protocol — no network, no key.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Protocol, cast

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel


@dataclass(frozen=True)
class LLMUsage:
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


@dataclass(frozen=True)
class StructuredResult[T: BaseModel]:
    data: T
    usage: LLMUsage


class LLMClient(Protocol):
    def structured[T: BaseModel](
        self, *, system: str, user: str, schema: type[T]
    ) -> StructuredResult[T]: ...


class GeminiLLMClient:
    """Google Gemini client that returns validated structured output + usage."""

    def __init__(self, *, api_key: str, model: str, temperature: float = 0.0) -> None:
        self._model = model
        self._chat = ChatGoogleGenerativeAI(
            model=model, google_api_key=api_key, temperature=temperature
        )

    def structured[T: BaseModel](
        self, *, system: str, user: str, schema: type[T]
    ) -> StructuredResult[T]:
        runnable = self._chat.with_structured_output(schema, include_raw=True)
        start = perf_counter()
        raw_result = runnable.invoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        latency_ms = (perf_counter() - start) * 1000.0
        result = cast(dict[str, object], raw_result)
        data = cast(T, result["parsed"])
        usage = _extract_usage(result.get("raw"), self._model, latency_ms)
        return StructuredResult(data=data, usage=usage)


def _extract_usage(raw: object, model: str, latency_ms: float) -> LLMUsage:
    meta = getattr(raw, "usage_metadata", None)
    input_tokens = 0
    output_tokens = 0
    if isinstance(meta, dict):
        input_tokens = int(meta.get("input_tokens", 0))
        output_tokens = int(meta.get("output_tokens", 0))
    return LLMUsage(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
    )
