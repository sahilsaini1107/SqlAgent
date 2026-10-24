"""Follow-ups are resolved against the conversation, not answered in isolation."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.agents.context import format_history, is_rewritten
from app.agents.contracts import Classification, Explanation, GeneratedSQL
from app.agents.llm import LLMUsage, StructuredResult

ClientFactory = Callable[["TurnScriptedLLM"], TestClient]  # the `make_client` fixture

CLARIFY_QUESTION = "Which metric should I rank the products by, e.g. revenue or units sold?"


class TurnScriptedLLM:
    """One scripted classification and generation per turn, recording every prompt."""

    def __init__(
        self, classifications: list[Classification], generations: list[GeneratedSQL]
    ) -> None:
        self._classifications = classifications
        self._generations = generations
        self.calls: list[tuple[str, str]] = []

    def structured(self, *, system: str, user: str, schema: type[BaseModel]):
        self.calls.append((schema.__name__, user))
        usage = LLMUsage(model="fake", input_tokens=1, output_tokens=1, latency_ms=0.0)
        if schema is Classification:
            return StructuredResult(data=self._classifications.pop(0), usage=usage)
        if schema is GeneratedSQL:
            return StructuredResult(data=self._generations.pop(0), usage=usage)
        if schema is Explanation:
            return StructuredResult(data=Explanation(explanation="Ranks products."), usage=usage)
        raise AssertionError(f"unexpected schema {schema!r}")

    def prompts(self, schema: str) -> list[str]:
        return [user for name, user in self.calls if name == schema]


def test_answer_to_a_clarification_keeps_the_original_subject(
    make_client: ClientFactory,
) -> None:
    llm = TurnScriptedLLM(
        classifications=[
            Classification(intent="generate", confidence=0.9),
            Classification(
                intent="follow_up",
                confidence=0.9,
                standalone_request="Top 5 products by revenue",
            ),
        ],
        generations=[
            GeneratedSQL(clarification=CLARIFY_QUESTION),
            GeneratedSQL(sql="SELECT id, name FROM products ORDER BY price DESC LIMIT 5"),
        ],
    )
    client = make_client(llm)

    first = client.post("/api/chat", json={"message": "top 5 products we have"}).json()
    assert first["status"] == "clarification_required"

    second = client.post(
        "/api/chat",
        json={"message": "by revenue", "conversation_id": first["conversation_id"]},
    ).json()

    # The classifier saw the earlier question and the assistant's clarifying question.
    classify_prompt = llm.prompts("Classification")[-1]
    assert "User: top 5 products we have" in classify_prompt
    assert CLARIFY_QUESTION in classify_prompt
    assert classify_prompt.endswith("by revenue")
    # Generation worked from the resolved, self-contained request.
    assert "Top 5 products by revenue" in llm.prompts("GeneratedSQL")[-1]
    assert second["status"] == "validated"
    assert second["interpreted_as"] == "Top 5 products by revenue"


def test_self_contained_message_is_not_reported_as_rewritten(
    make_client: ClientFactory,
) -> None:
    llm = TurnScriptedLLM(
        classifications=[
            Classification(
                intent="generate", confidence=0.9, standalone_request="Show all customers."
            )
        ],
        generations=[GeneratedSQL(sql="SELECT id FROM customers")],
    )
    body = make_client(llm).post(
        "/api/chat", json={"message": "show all customers"}
    ).json()
    assert body["interpreted_as"] is None
    # First turn: no transcript or previous query, so only the request itself is sent.
    assert llm.prompts("GeneratedSQL")[-1] == "Show all customers."


def test_new_topic_is_not_forced_to_modify_the_previous_query(
    make_client: ClientFactory,
) -> None:
    llm = TurnScriptedLLM(
        classifications=[
            Classification(intent="generate", confidence=0.9),
            Classification(intent="generate", confidence=0.9),
        ],
        generations=[
            GeneratedSQL(sql="SELECT id FROM customers"),
            GeneratedSQL(sql="SELECT carrier FROM shipments"),
        ],
    )
    client = make_client(llm)
    first = client.post("/api/chat", json={"message": "list customers"}).json()
    client.post(
        "/api/chat",
        json={"message": "late deliveries by carrier", "conversation_id": first["conversation_id"]},
    )
    prompt = llm.prompts("GeneratedSQL")[-1]
    assert "refine it only if the request builds on it" in prompt
    assert prompt.endswith("Request:\nlate deliveries by carrier")


def test_format_history_labels_turns_and_keeps_the_latest() -> None:
    messages = [
        {"role": "user", "content": "old question"},
        {"role": "assistant", "content": "x", "sql": "SELECT 1", "status": "executed"},
        {"role": "user", "content": "top 5 products we have"},
        {"role": "assistant", "content": CLARIFY_QUESTION, "status": "clarification_required"},
        {"role": "user", "content": "delete everything"},
        {"role": "assistant", "content": "I can only read.", "status": "refused"},
    ]
    text = format_history(messages, max_messages=4)
    assert text.splitlines() == [
        "User: top 5 products we have",
        f"Assistant asked for clarification: {CLARIFY_QUESTION}",
        "User: delete everything",
        "Assistant declined: I can only read.",
    ]
    assert "Assistant answered with SQL: SELECT 1" in format_history(messages)
    assert format_history([]) == ""


def test_is_rewritten_ignores_case_whitespace_and_trailing_punctuation() -> None:
    assert not is_rewritten("show all customers", "Show all  customers.")
    assert not is_rewritten("by revenue", "")
    assert is_rewritten("by revenue", "Top 5 products by revenue")
