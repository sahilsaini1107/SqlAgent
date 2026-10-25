"""Resilience and robustness regressions: LLM-failure handling, brace-safe prompt rendering,
dialect-transpile fallback, and atomic turn persistence."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.agents.llm import LLMError
from app.agents.prompt_loader import render_prompt
from app.api.routes_chat import _transpile

ClientFactory = Callable[[object], TestClient]


class RaisingLLM:
    """A client that always fails, standing in for a provider outage / unparseable output."""

    def structured(self, *, system: str, user: str, schema: type[BaseModel]):
        raise LLMError("simulated model failure")


def test_llm_failure_returns_graceful_error(make_client: ClientFactory) -> None:
    client = make_client(RaisingLLM())
    resp = client.post("/api/chat", json={"message": "show all customers"})
    # A model failure must not surface as a 500; the turn ends with a clean error status.
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error"
    assert body["error"]
    assert body["sql"] is None


def test_failed_turn_persists_both_messages(make_client: ClientFactory) -> None:
    client = make_client(RaisingLLM())
    conversation_id = client.post("/api/chat", json={"message": "hi"}).json()["conversation_id"]
    history = client.get(f"/api/conversations/{conversation_id}").json()["messages"]
    # The user message is never orphaned: user + assistant are written atomically.
    roles = [m["role"] for m in history]
    assert roles == ["user", "assistant"]
    assert history[1]["status"] == "error"


def test_render_prompt_is_brace_safe() -> None:
    # A schema comment containing braces (e.g. an allowed-value set) must not raise.
    schema = "orders(status TEXT)  -- status in {pending, shipped, delivered}"
    rendered = render_prompt("generate", schema=schema)
    assert "{pending, shipped, delivered}" in rendered
    assert "{schema}" not in rendered


def test_transpile_success_and_passthrough() -> None:
    # SQLite passthrough is a no-op and always "ok".
    assert _transpile("SELECT id FROM customers", "sqlite") == ("SELECT id FROM customers", True)
    # A real transpile succeeds and is flagged ok, so the response can label the dialect truthfully.
    rendered, ok = _transpile("SELECT id FROM customers LIMIT 1", "postgres")
    assert ok is True
    assert "customers" in rendered


def test_transpile_failure_flags_fallback(monkeypatch) -> None:
    # When transpilation fails, the original SQL is returned with ok=False so the caller reports
    # the SQL as the SQLite it actually is instead of mislabelling the dialect.
    import app.api.routes_chat as routes_chat

    def _boom(*_args, **_kwargs):
        raise ValueError("transpile exploded")

    monkeypatch.setattr(routes_chat.sqlglot, "transpile", _boom)
    fallback, ok = _transpile("SELECT 1", "postgres")
    assert ok is False
    assert fallback == "SELECT 1"
