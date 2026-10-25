"""Shared test fixtures."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agents.graph import build_agent_graph
from app.agents.llm import LLMClient
from app.db.build import build_sample_db
from app.dependencies import get_catalog, get_graph, get_session_store
from app.domain.schema_catalog import SchemaCatalog
from app.domain.sql_validator import SqlValidator
from app.infra.session_store import SessionStore
from app.infra.sqlite_adapter import SqliteReadOnlyAdapter
from app.main import app


@pytest.fixture(scope="session")
def sample_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The generated sample database, built once per test run. Tests only ever read it."""
    return build_sample_db(tmp_path_factory.mktemp("data") / "sample.sqlite")


@pytest.fixture
def make_client(tmp_path: Path, sample_db: Path) -> Iterator[Callable[[LLMClient], TestClient]]:
    """Build an API client whose agent graph runs on the given scripted LLM."""
    catalog = SchemaCatalog.from_sqlite(sample_db)
    adapter = SqliteReadOnlyAdapter(sample_db)
    validator = SqlValidator(catalog, execute_check=adapter.explain)
    store = SessionStore(tmp_path / "app.sqlite")

    def factory(llm: LLMClient, *, checkpointer: Any = None) -> TestClient:
        graph = build_agent_graph(
            client_for=lambda _node: llm,
            schema_summary=catalog.compact_summary(),
            validator=validator,
            adapter=adapter,
            checkpointer=checkpointer,
        )
        app.dependency_overrides[get_graph] = lambda: graph
        app.dependency_overrides[get_session_store] = lambda: store
        app.dependency_overrides[get_catalog] = lambda: catalog
        return TestClient(app)

    yield factory
    app.dependency_overrides.clear()
