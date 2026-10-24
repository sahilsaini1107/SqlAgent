"""Database adapter boundary.

A narrow protocol so the agent graph never talks to a raw driver. SQLite is the only
implementation today; a PostgreSQL adapter can be added later without touching the graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.domain.query_policy import QueryLimits


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    duration_ms: float


class DatabaseAdapter(Protocol):
    dialect: str

    def explain(self, sql: str) -> None:
        """Compile the query on the real engine; raise on syntax/schema errors."""

    def explain_plan(self, sql: str) -> list[str]:
        """Return the query plan steps (a cost/behaviour estimate) for a read-only query."""

    def execute_read_only(self, sql: str, limits: QueryLimits) -> QueryResult:
        """Execute a validated read-only query under row and time limits."""
