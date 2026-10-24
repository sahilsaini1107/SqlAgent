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


class MessageView(BaseModel):
    role: str
    content: str | None = None
    sql: str | None = None
    status: str | None = None
    created_at: str


class ConversationHistory(BaseModel):
    conversation_id: str
    messages: list[MessageView]
