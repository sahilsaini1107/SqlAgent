from __future__ import annotations

from typing import Any

from app.agents.contracts import GeneratedSQL
from app.agents.llm import LLMClient, LLMUsage
from app.agents.prompt_loader import load_prompt


def run_repair(
    *,
    user_input: str,
    schema_summary: str,
    failed_sql: str,
    issues: list[dict[str, Any]],
    client: LLMClient,
) -> tuple[GeneratedSQL, LLMUsage]:
    system = load_prompt("repair").format(schema=schema_summary)
    issue_lines = "\n".join(f"- {i.get('code')}: {i.get('message')}" for i in issues)
    user = (
        f"Original request:\n{user_input}\n\n"
        f"Invalid SQL:\n{failed_sql}\n\n"
        f"Validation errors:\n{issue_lines}\n\n"
        "Return corrected SQL."
    )
    result = client.structured(system=system, user=user, schema=GeneratedSQL)
    return result.data, result.usage
