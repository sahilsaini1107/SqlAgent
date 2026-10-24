"""FastAPI dependencies. Each resolves a piece of the runtime; tests override them."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.domain.schema_catalog import SchemaCatalog
from app.infra.session_store import SessionStore
from app.runtime import Runtime, build_runtime


@lru_cache(maxsize=1)
def get_runtime() -> Runtime:
    return build_runtime()


def get_graph() -> Any:
    return get_runtime().graph


def get_session_store() -> SessionStore:
    return get_runtime().session_store


def get_catalog() -> SchemaCatalog:
    return get_runtime().catalog
