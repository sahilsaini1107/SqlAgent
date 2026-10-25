from __future__ import annotations

from app.agents.contracts import GeneratedSQL
from app.agents.llm import LLMClient, LLMUsage
from app.agents.prompt_loader import render_prompt


def run_generate(
    *,
    user_input: str,
    schema_summary: str,
    previous_sql: str | None,
    client: LLMClient,
    history: str = "",
) -> tuple[GeneratedSQL, LLMUsage]:
    system = render_prompt("generate", schema=schema_summary)
    user = _build_user_message(user_input, previous_sql, history)
    result = client.structured(system=system, user=user, schema=GeneratedSQL)
    return result.data, result.usage


def _build_user_message(user_input: str, previous_sql: str | None, history: str) -> str:
    parts: list[str] = []
    if history:
        parts.append(f"Conversation so far (oldest first):\n{history}")
    if previous_sql:
        parts.append(
            "Previous query (refine it only if the request builds on it; otherwise write a new "
            f"query):\n{previous_sql}"
        )
    if not parts:
        return user_input
    parts.append(f"Request:\n{user_input}")
    return "\n\n".join(parts)
