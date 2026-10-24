from __future__ import annotations

from app.agents.contracts import Classification
from app.agents.llm import LLMClient, LLMUsage
from app.agents.prompt_loader import load_prompt


def run_classify(
    user_input: str, client: LLMClient, *, history: str = ""
) -> tuple[Classification, LLMUsage]:
    result = client.structured(
        system=load_prompt("classify"),
        user=_build_user_message(user_input, history),
        schema=Classification,
    )
    return result.data, result.usage


def _build_user_message(user_input: str, history: str) -> str:
    if not history:
        return f"Latest message:\n{user_input}"
    return f"Conversation so far (oldest first):\n{history}\n\nLatest message:\n{user_input}"
