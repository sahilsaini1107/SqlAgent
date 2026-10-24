"""Graph routing tests with a fake LLM — no network, no API key."""

from __future__ import annotations

from pydantic import BaseModel

from app.agents.contracts import Classification, GeneratedSQL
from app.agents.graph import build_agent_graph
from app.agents.llm import LLMUsage, StructuredResult

SCHEMA = "customers(id INTEGER PK, state TEXT)"


class FakeLLM:
    """Returns canned structured output based on the requested schema type."""

    def __init__(self, classification: Classification, generation: GeneratedSQL) -> None:
        self._classification = classification
        self._generation = generation

    def structured(self, *, system: str, user: str, schema: type[BaseModel]):
        usage = LLMUsage(model="fake", input_tokens=1, output_tokens=1, latency_ms=0.0)
        if schema is Classification:
            return StructuredResult(data=self._classification, usage=usage)
        if schema is GeneratedSQL:
            return StructuredResult(data=self._generation, usage=usage)
        raise AssertionError(f"unexpected schema {schema!r}")


def _graph(classification: Classification, generation: GeneratedSQL | None = None):
    fake = FakeLLM(classification, generation or GeneratedSQL(sql="SELECT 1"))
    return build_agent_graph(client_for=lambda _node: fake, schema_summary=SCHEMA)


def test_generate_intent_produces_candidate_sql() -> None:
    graph = _graph(
        Classification(intent="generate", confidence=0.9),
        GeneratedSQL(sql="SELECT * FROM customers", assumptions=["returns all rows"]),
    )
    out = graph.invoke({"user_input": "show all customers"})
    assert out["intent"] == "generate"
    assert out["candidate_sql"] == "SELECT * FROM customers"
    assert out["status"] == "generated"
    nodes = {u["node"] for u in out["usages"]}
    assert nodes == {"classify", "generate"}


def test_out_of_scope_is_refused() -> None:
    graph = _graph(Classification(intent="out_of_scope", confidence=0.95))
    out = graph.invoke({"user_input": "who won the world cup?"})
    assert out["status"] == "refused"
    assert out.get("candidate_sql") is None
    assert "SQL" in out["refusal"]


def test_destructive_is_refused() -> None:
    graph = _graph(Classification(intent="destructive", confidence=0.95))
    out = graph.invoke({"user_input": "delete all customers"})
    assert out["status"] == "refused"
    assert "read-only" in out["refusal"].lower()


def test_ambiguous_generation_asks_for_clarification() -> None:
    graph = _graph(
        Classification(intent="generate", confidence=0.4),
        GeneratedSQL(sql=None, clarification="Which table did you mean?"),
    )
    out = graph.invoke({"user_input": "show me the stuff"})
    assert out["status"] == "clarification_required"
    assert out["clarification"] == "Which table did you mean?"
    assert out.get("candidate_sql") is None
