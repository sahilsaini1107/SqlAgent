from __future__ import annotations

from app.agents.contracts import GeneratedSQL
from app.agents.llm import LLMClient, LLMUsage
from app.agents.prompt_loader import load_prompt


def run_generate(
    *,
    user_input: str,
    schema_summary: str,
    previous_sql: str | None,
    client: LLMClient,
) -> tuple[GeneratedSQL, LLMUsage]:
    system = load_prompt("generate").format(schema=schema_summary)
    user = _build_user_message(user_input, previous_sql)
    result = client.structured(system=system, user=user, schema=GeneratedSQL)
    return result.data, result.usage


def _build_user_message(user_input: str, previous_sql: str | None) -> str:
    if previous_sql:
        return (
            f"Previous query:\n{previous_sql}\n\n"
            f"Modify it to satisfy this request:\n{user_input}"
        )
    return user_input
