"""Chat API tests — offline. A scripted fake LLM is injected via dependency overrides."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.agents.contracts import Classification, Explanation, GeneratedSQL
from app.agents.graph import build_agent_graph
from app.agents.llm import LLMUsage, StructuredResult
from app.db.build import build_sample_db
from app.dependencies import get_catalog, get_graph, get_session_store
from app.domain.schema_catalog import SchemaCatalog
from app.domain.sql_validator import SqlValidator
from app.infra.session_store import SessionStore
from app.infra.sqlite_adapter import SqliteReadOnlyAdapter
from app.main import app


class ScriptedLLM:
    def __init__(
        self,
        classification: Classification,
        generations: list[GeneratedSQL] | None = None,
        explanation: str = "This query returns rows from the database.",
    ) -> None:
        self._classification = classification
        self._generations = generations or [GeneratedSQL(sql="SELECT * FROM customers")]
        self._index = 0
        self._explanation = explanation

    def structured(self, *, system: str, user: str, schema: type[BaseModel]):
        usage = LLMUsage(model="fake", input_tokens=1, output_tokens=1, latency_ms=0.0)
        if schema is Classification:
            return StructuredResult(data=self._classification, usage=usage)
        if schema is GeneratedSQL:
            gen = self._generations[min(self._index, len(self._generations) - 1)]
            self._index += 1
            return StructuredResult(data=gen, usage=usage)
        if schema is Explanation:
            return StructuredResult(data=Explanation(explanation=self._explanation), usage=usage)
        raise AssertionError(f"unexpected schema {schema!r}")


ClientFactory = Callable[[ScriptedLLM], TestClient]


@pytest.fixture
def make_client(tmp_path: Path) -> Iterator[ClientFactory]:
    db = build_sample_db(tmp_path / "q.sqlite")
    catalog = SchemaCatalog.from_sqlite(db)
    adapter = SqliteReadOnlyAdapter(db)
    validator = SqlValidator(catalog, execute_check=adapter.explain)
    store = SessionStore(tmp_path / "app.sqlite")

    def factory(llm: ScriptedLLM) -> TestClient:
        graph = build_agent_graph(
            client_for=lambda _node: llm,
            schema_summary=catalog.compact_summary(),
            validator=validator,
            adapter=adapter,
        )
        app.dependency_overrides[get_graph] = lambda: graph
        app.dependency_overrides[get_session_store] = lambda: store
        app.dependency_overrides[get_catalog] = lambda: catalog
        return TestClient(app)

    yield factory
    app.dependency_overrides.clear()


def test_generate_returns_sql_and_explanation(make_client: ClientFactory) -> None:
    client = make_client(ScriptedLLM(Classification(intent="generate", confidence=0.9)))
    resp = client.post("/api/chat", json={"message": "show all customers"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "validated"
    assert body["sql"]
    assert body["explanation"]
    assert body["validation"]["passed"] is True
    assert body["conversation_id"]
    assert body["trace_id"]


def test_out_of_scope_is_refused(make_client: ClientFactory) -> None:
    client = make_client(ScriptedLLM(Classification(intent="out_of_scope", confidence=0.9)))
    body = client.post("/api/chat", json={"message": "who won the world cup?"}).json()
    assert body["status"] == "refused"
    assert body["sql"] is None
    assert body["refusal"]


def test_execution_returns_result(make_client: ClientFactory) -> None:
    client = make_client(
        ScriptedLLM(
            Classification(intent="generate", confidence=0.9),
            [GeneratedSQL(sql="SELECT id FROM customers ORDER BY id")],
        )
    )
    body = client.post("/api/chat", json={"message": "list ids", "execute": True}).json()
    assert body["status"] == "executed"
    assert body["result"]["row_count"] == 8


def test_history_and_followup_context(make_client: ClientFactory) -> None:
    client = make_client(ScriptedLLM(Classification(intent="generate", confidence=0.9)))
    first = client.post("/api/chat", json={"message": "show all customers"}).json()
    conversation_id = first["conversation_id"]

    # Second turn on the same conversation.
    client.post(
        "/api/chat",
        json={"message": "only California", "conversation_id": conversation_id},
    )

    history = client.get(f"/api/conversations/{conversation_id}").json()
    assert len(history["messages"]) == 4
    assert history["messages"][0]["role"] == "user"


def test_unknown_conversation_returns_404(make_client: ClientFactory) -> None:
    client = make_client(ScriptedLLM(Classification(intent="generate", confidence=0.9)))
    resp = client.post("/api/chat", json={"message": "x", "conversation_id": "missing"})
    assert resp.status_code == 404


def test_schema_endpoint(make_client: ClientFactory) -> None:
    client = make_client(ScriptedLLM(Classification(intent="generate", confidence=0.9)))
    body = client.get("/api/schema").json()
    assert body["dialect"] == "sqlite"
    assert {t["name"] for t in body["tables"]} == {"customers", "products", "orders", "order_items"}
