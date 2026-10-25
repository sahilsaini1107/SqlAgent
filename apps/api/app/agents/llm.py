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


class LLMError(RuntimeError):
    """A model call failed or returned output that did not satisfy its schema."""


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

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        temperature: float = 0.0,
        timeout_s: float = 30.0,
        max_retries: int = 2,
        max_output_tokens: int = 2048,
    ) -> None:
        self._model = model
        # timeout + max_retries make a transient 429/503/network error non-fatal (the client
        # retries with backoff) and stop a hung call from tying up a worker indefinitely.
        self._chat = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
            timeout=timeout_s,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
        )

    def structured[T: BaseModel](
        self, *, system: str, user: str, schema: type[T]
    ) -> StructuredResult[T]:
        runnable = self._chat.with_structured_output(schema, include_raw=True)
        start = perf_counter()
        messages = [SystemMessage(content=system), HumanMessage(content=user)]
        try:
            raw_result = runnable.invoke(messages)
        except Exception as err:  # transient/provider error after the client's own retries
            raise LLMError(f"model call failed: {err}") from err
        latency_ms = (perf_counter() - start) * 1000.0
        result = cast(dict[str, object], raw_result)
        parsed = result.get("parsed")
        if parsed is None:
            # include_raw=True sets parsed=None and populates parsing_error when the model
            # returns output that fails schema validation. Surface it as a typed error instead
            # of handing a None downstream where it becomes an opaque AttributeError.
            raise LLMError(f"model returned unparseable output: {result.get('parsing_error')}")
        usage = _extract_usage(result.get("raw"), self._model, latency_ms)
        return StructuredResult(data=cast(T, parsed), usage=usage)


def _extract_usage(raw: object, model: str, latency_ms: float) -> LLMUsage:
    meta = getattr(raw, "usage_metadata", None)
    input_tokens = 0
    output_tokens = 0
    # usage_metadata is normally a dict, but some provider paths surface it as an object with
    # attributes — read both so cost telemetry doesn't silently report zero.
    if isinstance(meta, dict):
        input_tokens = int(meta.get("input_tokens", 0) or 0)
        output_tokens = int(meta.get("output_tokens", 0) or 0)
    elif meta is not None:
        input_tokens = int(getattr(meta, "input_tokens", 0) or 0)
        output_tokens = int(getattr(meta, "output_tokens", 0) or 0)
    return LLMUsage(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
    )
