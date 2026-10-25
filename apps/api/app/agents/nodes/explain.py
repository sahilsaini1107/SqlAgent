from __future__ import annotations

from app.agents.contracts import Explanation
from app.agents.llm import LLMClient, LLMUsage
from app.agents.prompt_loader import render_prompt


def run_explain(
    *, final_sql: str, schema_summary: str, client: LLMClient, user_request: str = ""
) -> tuple[Explanation, LLMUsage]:
    system = render_prompt("explain", schema=schema_summary)
    # Include the original request so the explanation can speak to what was asked/fixed (e.g. a
    # debug turn referencing the broken column), not just describe the corrected SQL in a vacuum.
    if user_request:
        user = f"User request:\n{user_request}\n\nValidated SQL:\n{final_sql}"
    else:
        user = final_sql
    result = client.structured(system=system, user=user, schema=Explanation)
    return result.data, result.usage


def run_answer(
    *, user_input: str, schema_summary: str, client: LLMClient
) -> tuple[Explanation, LLMUsage]:
    system = render_prompt("answer", schema=schema_summary)
    result = client.structured(system=system, user=user_input, schema=Explanation)
    return result.data, result.usage
