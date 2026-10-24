"""Conversation context for the agent.

Turns the stored transcript into a short, model-facing summary of the recent exchange, so the
classifier can resolve follow-ups ("by revenue", "only those in 2025", answers to a
clarifying question) into self-contained requests, and generation can see what was asked.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

MAX_MESSAGES = 6
MAX_TEXT_CHARS = 400
MAX_SQL_CHARS = 1200


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def format_history(messages: Sequence[dict[str, Any]], *, max_messages: int = MAX_MESSAGES) -> str:
    """Render the last few stored messages, oldest first. Empty when there is no history."""
    lines: list[str] = []
    for message in list(messages)[-max_messages:]:
        content = _clip(message.get("content") or "", MAX_TEXT_CHARS)
        if message.get("role") == "user":
            lines.append(f"User: {content}")
            continue
        status = message.get("status")
        sql = message.get("sql")
        if status == "clarification_required":
            lines.append(f"Assistant asked for clarification: {content}")
        elif status == "refused":
            lines.append(f"Assistant declined: {content}")
        elif sql:
            sql_text = _clip(sql, MAX_SQL_CHARS)
            lines.append(f"Assistant answered with SQL: {sql_text}")
        elif content:
            lines.append(f"Assistant: {content}")
    return "\n".join(lines)


def is_rewritten(original: str, resolved: str) -> bool:
    """True when the resolved request says something the original message did not."""

    def norm(text: str) -> str:
        return " ".join(text.lower().split()).rstrip("?.! ")

    return bool(resolved.strip()) and norm(original) != norm(resolved)
