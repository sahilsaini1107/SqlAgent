"""Graph routing tests with a fake LLM — no network, no API key.

The validator and read-only adapter are real (built against a temporary sample database), so
these also exercise the validation gate and the repair loop end to end.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest
from pydantic import BaseModel

from app.agents.contracts import Classification, Explanation, GeneratedSQL
from app.agents.graph import build_agent_graph
from app.agents.llm import LLMUsage, StructuredResult
from app.db.seed_data import WAREHOUSES
from app.domain.schema_catalog import SchemaCatalog
from app.domain.sql_validator import SqlValidator
from app.infra.sqlite_adapter import SqliteReadOnlyAdapter

SCHEMA = "customers(id, name, state); orders(id, customer_id)"


class FakeLLM:
    """Returns a canned classification and a queue of generations (one per LLM call)."""

    def __init__(self, classification: Classification, generations: Iterable[GeneratedSQL]) -> None:
        self._classification = classification
        self._generations = list(generations)
        self._index = 0

    def structured(self, *, system: str, user: str, schema: type[BaseModel]):
        usage = LLMUsage(model="fake", input_tokens=1, output_tokens=1, latency_ms=0.0)
        if schema is Classification:
            return StructuredResult(data=self._classification, usage=usage)
        if schema is GeneratedSQL:
            gen = self._generations[min(self._index, len(self._generations) - 1)]
            self._index += 1
            return StructuredResult(data=gen, usage=usage)
        if schema is Explanation:
            return StructuredResult(data=Explanation(explanation="It returns rows."), usage=usage)
        raise AssertionError(f"unexpected schema {schema!r}")


@pytest.fixture
def deps(sample_db: Path):
    db = sample_db
    catalog = SchemaCatalog.from_sqlite(db)
    adapter = SqliteReadOnlyAdapter(db)
    validator = SqlValidator(catalog, execute_check=adapter.explain)
    return validator, adapter


def _graph(deps, classification, generations=None):
    validator, adapter = deps
    fake = FakeLLM(classification, generations or [GeneratedSQL(sql="SELECT 1")])
    return build_agent_graph(
        client_for=lambda _node: fake,
        schema_summary=SCHEMA,
        validator=validator,
        adapter=adapter,
    )


def test_valid_generation_passes_validation(deps) -> None:
    graph = _graph(
        deps,
        Classification(intent="generate", confidence=0.9),
        [GeneratedSQL(sql="SELECT * FROM customers")],
    )
    out = graph.invoke({"user_input": "show all customers"})
    assert out["status"] == "validated"
    assert out["final_sql"]
    assert out["explanation"]
    assert {"classify", "generate", "explain"} <= {u["node"] for u in out["usages"]}


def test_out_of_scope_is_refused(deps) -> None:
    out = _graph(deps, Classification(intent="out_of_scope", confidence=0.95)).invoke(
        {"user_input": "who won the world cup?"}
    )
    assert out["status"] == "refused"
    assert out.get("final_sql") is None
    assert "SQL" in out["refusal"]


def test_destructive_is_refused(deps) -> None:
    out = _graph(deps, Classification(intent="destructive", confidence=0.95)).invoke(
        {"user_input": "delete all customers"}
    )
    assert out["status"] == "refused"
    assert "read-only" in out["refusal"].lower()


def test_ambiguous_generation_asks_for_clarification(deps) -> None:
    graph = _graph(
        deps,
        Classification(intent="generate", confidence=0.4),
        [GeneratedSQL(sql=None, clarification="Which table did you mean?")],
    )
    out = graph.invoke({"user_input": "show me the stuff"})
    assert out["status"] == "clarification_required"
    assert out["clarification"] == "Which table did you mean?"
    assert out.get("final_sql") is None


def test_invalid_sql_is_repaired(deps) -> None:
    graph = _graph(
        deps,
        Classification(intent="generate", confidence=0.9),
        [GeneratedSQL(sql="SELECT * FROM employees"), GeneratedSQL(sql="SELECT * FROM customers")],
    )
    out = graph.invoke({"user_input": "show all customers"})
    assert out["status"] == "validated"
    assert out["final_sql"]
    assert out["retry_count"] == 1


def test_repair_is_bounded(deps) -> None:
    graph = _graph(
        deps,
        Classification(intent="generate", confidence=0.9),
        [GeneratedSQL(sql="SELECT * FROM employees")],  # always invalid
    )
    out = graph.invoke({"user_input": "show all customers"})
    assert out["status"] == "validation_failed"
    assert out.get("final_sql") is None
    assert out["retry_count"] == 2


def test_execution_returns_rows(deps) -> None:
    graph = _graph(
        deps,
        Classification(intent="generate", confidence=0.9),
        [GeneratedSQL(sql="SELECT id FROM warehouses ORDER BY id")],
    )
    out = graph.invoke({"user_input": "list ids", "execution_requested": True})
    assert out["status"] == "executed"
    assert out["query_result"]["row_count"] == len(WAREHOUSES)
