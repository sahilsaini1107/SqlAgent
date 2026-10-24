from __future__ import annotations

from app.agents.contracts import GeneratedSQL
from app.agents.llm import LLMClient, LLMUsage
from app.agents.prompt_loader import load_prompt


def run_optimize(
    *, user_input: str, schema_summary: str, client: LLMClient
) -> tuple[GeneratedSQL, LLMUsage]:
    system = load_prompt("optimize").format(schema=schema_summary)
    result = client.structured(system=system, user=user_input, schema=GeneratedSQL)
    return result.data, result.usage
