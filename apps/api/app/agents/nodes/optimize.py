from __future__ import annotations

from app.agents.contracts import GeneratedSQL
from app.agents.llm import LLMClient, LLMUsage
from app.agents.prompt_loader import render_prompt


def run_optimize(
    *,
    user_input: str,
    schema_summary: str,
    client: LLMClient,
    previous_sql: str | None = None,
    history: str = "",
) -> tuple[GeneratedSQL, LLMUsage]:
    system = render_prompt("optimize", schema=schema_summary)
    user = _build_user_message(user_input, previous_sql, history)
    result = client.structured(system=system, user=user, schema=GeneratedSQL)
    return result.data, result.usage


def _build_user_message(user_input: str, previous_sql: str | None, history: str) -> str:
    parts: list[str] = []
    if history:
        parts.append(f"Conversation so far (oldest first):\n{history}")
    # "optimize that" refers to the last query; without it the node has nothing to optimize.
    if previous_sql:
        parts.append(f"Query to optimize:\n{previous_sql}")
    parts.append(f"Request:\n{user_input}")
    return "\n\n".join(parts)
