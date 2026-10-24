from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ValidationView(BaseModel):
    passed: bool
    issues: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)


class ResultView(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    duration_ms: float


class UsageCall(BaseModel):
    node: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


class UsageView(BaseModel):
    calls: list[UsageCall] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    llm_calls: int = 0


class ChatResponse(BaseModel):
    conversation_id: str
    trace_id: str
    intent: str | None = None
    status: str
    sql: str | None = None
    explanation: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    clarification: str | None = None
    refusal: str | None = None
    validation: ValidationView
    result: ResultView | None = None
    # SQL dialect the `sql` field is rendered in, and the query plan (cost estimate).
    dialect: str = "sqlite"
    plan: list[str] | None = None
    # Per-LLM-call token/latency telemetry for this turn.
    usage: UsageView | None = None
    # The request as the agent understood it, when it differs from the message (a follow-up
    # resolved against the conversation, or a vague prompt made explicit).
    interpreted_as: str | None = None


class MessageView(BaseModel):
    role: str
    content: str | None = None
    sql: str | None = None
    status: str | None = None
    created_at: str


class ConversationHistory(BaseModel):
    conversation_id: str
    messages: list[MessageView]
