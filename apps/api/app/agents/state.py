"""The LangGraph agent state.

A single typed dict threaded through the graph. Each node reads what it needs and returns
only the fields it owns; ``usages`` accumulates one telemetry record per LLM call across the
whole run (token counts + latency) for traceability.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict


class AgentState(TypedDict, total=False):
    # Input
    user_input: str
    previous_valid_sql: str | None
    execution_requested: bool

    # Context
    schema_summary: str

    # Routing / generation
    intent: str
    candidate_sql: str | None
    assumptions: list[str]
    clarification: str | None
    refusal: str | None

    # Validation / execution
    final_sql: str | None
    validation_issues: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    retry_count: int
    query_result: dict[str, Any] | None
    query_plan: list[str] | None

    # Output
    explanation: str | None

    status: str

    # Telemetry — accumulated across nodes.
    usages: Annotated[list[dict[str, Any]], add]
