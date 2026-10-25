from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    execute: bool = False
    # Dialect to render the SQL in. Validation/execution run on SQLite; other dialects are
    # produced by transpiling the validated query.
    dialect: Literal["sqlite", "postgres", "mysql"] = "sqlite"
    # Stream only: resume a previously interrupted run from its last checkpoint instead of
    # starting a new one. The value is the run_id from that run's `start` event.
    resume_run_id: str | None = Field(default=None, max_length=64)
