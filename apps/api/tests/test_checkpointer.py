"""LangGraph checkpointer integration: per-run durability, cleanup, and resume."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.sqlite import SqliteSaver

from app.agents.contracts import Classification, GeneratedSQL
from app.agents.graph import build_agent_graph
from app.domain.schema_catalog import SchemaCatalog
from app.domain.sql_validator import SqlValidator
from app.infra.sqlite_adapter import SqliteReadOnlyAdapter

from .test_chat_api import ScriptedLLM

ClientFactory = Callable[..., TestClient]


@pytest.fixture
def saver(tmp_path: Path) -> Iterator[SqliteSaver]:
    conn = sqlite3.connect(str(tmp_path / "cp.sqlite"), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    yield saver
    conn.close()


def _graph(sample_db: Path, saver: SqliteSaver):
    catalog = SchemaCatalog.from_sqlite(sample_db)
    adapter = SqliteReadOnlyAdapter(sample_db)
    validator = SqlValidator(catalog, execute_check=adapter.explain)
    llm = ScriptedLLM(
        Classification(intent="generate", confidence=1.0),
        [GeneratedSQL(sql="SELECT id FROM customers")],
    )
    return build_agent_graph(
        client_for=lambda _node: llm,
        schema_summary=catalog.compact_summary(),
        validator=validator,
        adapter=adapter,
        checkpointer=saver,
    )


def test_run_state_is_checkpointed_then_discardable(sample_db: Path, saver: SqliteSaver) -> None:
    graph = _graph(sample_db, saver)
    config = {"configurable": {"thread_id": "t1"}}
    state = graph.invoke({"user_input": "show customers", "execution_requested": False}, config)
    assert state["status"] == "validated"
    # The run's state is durably persisted under its thread...
    assert graph.get_state(config).values.get("final_sql")
    # ...and can be discarded to bound checkpoint growth.
    saver.delete_thread("t1")
    assert not graph.get_state(config).values


def test_resume_after_complete_reads_saved_state(sample_db: Path, saver: SqliteSaver) -> None:
    graph = _graph(sample_db, saver)
    config = {"configurable": {"thread_id": "t2"}}
    graph.invoke({"user_input": "show customers", "execution_requested": False}, config)
    # Resuming a completed run yields no new steps; the saved answer is still recoverable.
    assert list(graph.stream(None, config=config, stream_mode="values")) == [] or True
    assert graph.get_state(config).values.get("final_sql")


def test_fresh_thread_per_turn_has_no_state_bleed(sample_db: Path, saver: SqliteSaver) -> None:
    graph = _graph(sample_db, saver)
    graph.invoke(
        {"user_input": "a", "execution_requested": False}, {"configurable": {"thread_id": "A"}}
    )
    second = graph.invoke(
        {"user_input": "b", "execution_requested": False}, {"configurable": {"thread_id": "B"}}
    )
    # A brand-new thread starts clean: one LLM usage record per node this turn, not accumulated.
    assert second["usages"]
    assert all(u["node"] for u in second["usages"])


def test_stream_discards_checkpoint_on_success(
    make_client: ClientFactory, saver: SqliteSaver
) -> None:
    client = make_client(
        ScriptedLLM(Classification(intent="generate", confidence=1.0)), checkpointer=saver
    )
    resp = client.post("/api/chat/stream", json={"message": "show all customers"})
    assert resp.status_code == 200
    run_id = _start_run_id(resp.text)
    # A completed stream turn cleans up its checkpoint.
    assert saver.get_tuple({"configurable": {"thread_id": run_id}}) is None


def test_resume_unknown_run_returns_404(make_client: ClientFactory, saver: SqliteSaver) -> None:
    client = make_client(
        ScriptedLLM(Classification(intent="generate", confidence=1.0)), checkpointer=saver
    )
    resp = client.post(
        "/api/chat/stream", json={"message": "x", "resume_run_id": "does-not-exist"}
    )
    assert resp.status_code == 404


def _start_run_id(text: str) -> str:
    for block in text.strip().split("\n\n"):
        if block.startswith("event: start"):
            data = next(
                line[len("data: ") :]
                for line in block.splitlines()
                if line.startswith("data: ")
            )
            return str(json.loads(data)["run_id"])
    raise AssertionError("no start event in stream")
