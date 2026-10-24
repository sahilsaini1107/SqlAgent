from __future__ import annotations

from app.agents.contracts import Classification
from app.agents.llm import LLMClient, LLMUsage
from app.agents.prompt_loader import load_prompt


def run_classify(user_input: str, client: LLMClient) -> tuple[Classification, LLMUsage]:
    result = client.structured(
        system=load_prompt("classify"), user=user_input, schema=Classification
    )
    return result.data, result.usage
