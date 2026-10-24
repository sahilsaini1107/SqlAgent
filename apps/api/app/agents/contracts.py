"""Typed contracts for structured LLM output.

Every LLM call in the graph returns one of these validated models — the nodes never parse
free-form text. This keeps the agent deterministic at its boundaries and makes malformed
model output a caught error rather than a silent bug.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Intent = Literal[
    "generate",
    "follow_up",
    "debug",
    "optimize",
    "explain",
    "sql_concept",
    "destructive",
    "out_of_scope",
    "clarify",
]


class Classification(BaseModel):
    intent: Intent
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""


class GeneratedSQL(BaseModel):
    sql: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    clarification: str | None = None


class Explanation(BaseModel):
    explanation: str
