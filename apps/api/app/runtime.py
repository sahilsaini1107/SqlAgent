"""Compose the application's runtime components once (catalog, graph, session store).

Building the graph does not require the API key — the Gemini client is created lazily on the
first LLM call — so this is safe to construct at startup. The read-only adapter and validator
are bound to the sample database here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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


def build_runtime() -> Runtime:
    catalog = SchemaCatalog.from_sqlite(settings.sample_db_path)
    adapter = SqliteReadOnlyAdapter(settings.sample_db_path)
    validator = SqlValidator(catalog, execute_check=adapter.explain)
    graph = build_agent_graph(
        client_for=default_client_for(),
        schema_summary=catalog.compact_summary(),
        validator=validator,
        adapter=adapter,
        limits=QueryLimits(max_rows=settings.max_rows, timeout_ms=settings.query_timeout_ms),
    )
    return Runtime(catalog=catalog, graph=graph, session_store=SessionStore(settings.app_db_path))
