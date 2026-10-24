from __future__ import annotations

from app.agents.contracts import Explanation
from app.agents.llm import LLMClient, LLMUsage
from app.agents.prompt_loader import load_prompt


def run_explain(
    *, final_sql: str, schema_summary: str, client: LLMClient
) -> tuple[Explanation, LLMUsage]:
    system = load_prompt("explain").format(schema=schema_summary)
    result = client.structured(system=system, user=final_sql, schema=Explanation)
    return result.data, result.usage


def run_answer(
    *, user_input: str, schema_summary: str, client: LLMClient
) -> tuple[Explanation, LLMUsage]:
    system = load_prompt("answer").format(schema=schema_summary)
    result = client.structured(system=system, user=user_input, schema=Explanation)
    return result.data, result.usage
