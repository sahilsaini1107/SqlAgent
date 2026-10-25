"""Compose the application's runtime components once (catalog, graph, session store).

Building the graph does not require the API key — the Gemini client is created lazily on the
first LLM call — so this is safe to construct at startup. The read-only adapter and validator
are bound to the sample database here.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver

from app.agents.factory import default_client_for
from app.agents.graph import build_agent_graph
from app.config import settings
from app.domain.query_policy import QueryLimits
from app.domain.schema_catalog import SchemaCatalog
from app.domain.sql_validator import SqlValidator
from app.infra.session_store import SessionStore
from app.infra.sqlite_adapter import SqliteReadOnlyAdapter


@dataclass(frozen=True)
class Runtime:
    catalog: SchemaCatalog
    graph: Any
    session_store: SessionStore
    checkpointer: Any


def _build_checkpointer() -> SqliteSaver:
    """Durable per-run graph state. check_same_thread=False because FastAPI serves sync
    endpoints from a threadpool; SqliteSaver guards the shared connection with its own lock."""
    settings.checkpoint_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(settings.checkpoint_db_path), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


def build_runtime() -> Runtime:
    catalog = SchemaCatalog.from_sqlite(settings.sample_db_path)
    adapter = SqliteReadOnlyAdapter(settings.sample_db_path)
    validator = SqlValidator(catalog, execute_check=adapter.explain)
    checkpointer = _build_checkpointer()
    graph = build_agent_graph(
        client_for=default_client_for(),
        schema_summary=catalog.compact_summary(),
        validator=validator,
        adapter=adapter,
        limits=QueryLimits(max_rows=settings.max_rows, timeout_ms=settings.query_timeout_ms),
        checkpointer=checkpointer,
    )
    return Runtime(
        catalog=catalog,
        graph=graph,
        session_store=SessionStore(settings.app_db_path),
        checkpointer=checkpointer,
    )
