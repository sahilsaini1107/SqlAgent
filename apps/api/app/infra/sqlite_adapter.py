"""Read-only SQLite adapter — the independent enforcement layer.

Four layers of defense, so that even a validator bug cannot cause a write or a dangerous call:
1. The connection is opened ``mode=ro`` (the file is never writable).
2. ``PRAGMA query_only=ON`` rejects writes at the engine.
3. An authorizer callback allows only SELECT/READ and allowlisted functions; everything else
   (ATTACH, PRAGMA, load_extension, writes, ...) is denied.
4. A progress handler enforces a wall-clock timeout, and results are capped by row count.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from app.domain.query_policy import ALLOWED_FUNCTIONS, QueryLimits
from app.infra.db_adapter import QueryResult

_ALLOW = sqlite3.SQLITE_OK
_DENY = sqlite3.SQLITE_DENY
_PROGRESS_INSTRUCTIONS = 1000


class SqliteReadOnlyAdapter:
    dialect = "sqlite"

    def __init__(
        self, db_path: Path, *, allowed_functions: frozenset[str] = ALLOWED_FUNCTIONS
    ) -> None:
        self._db_path = db_path
        self._allowed = {f.lower() for f in allowed_functions}

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        conn.execute("PRAGMA query_only = ON")
        conn.set_authorizer(self._authorizer)
        return conn

    def _authorizer(
        self,
        action: int,
        arg1: str | None,
        arg2: str | None,
        dbname: str | None,
        source: str | None,
    ) -> int:
        if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ):
            return _ALLOW
        if action == sqlite3.SQLITE_FUNCTION:
            return _ALLOW if (arg2 or "").lower() in self._allowed else _DENY
        recursive = getattr(sqlite3, "SQLITE_RECURSIVE", None)
        if recursive is not None and action == recursive:
            return _ALLOW
        return _DENY

    def explain(self, sql: str) -> None:
        conn = self._connect()
        try:
            conn.execute("EXPLAIN " + sql).fetchall()
        finally:
            conn.close()

    def execute_read_only(self, sql: str, limits: QueryLimits) -> QueryResult:
        conn = self._connect()
        try:
            deadline = time.monotonic() + limits.timeout_ms / 1000.0
            conn.set_progress_handler(
                lambda: 1 if time.monotonic() > deadline else 0, _PROGRESS_INSTRUCTIONS
            )
            start = time.perf_counter()
            cursor = conn.execute(sql)
            fetched = cursor.fetchmany(limits.max_rows + 1)
            duration_ms = (time.perf_counter() - start) * 1000.0
            columns = [d[0] for d in cursor.description] if cursor.description else []
            truncated = len(fetched) > limits.max_rows
            rows = [list(row) for row in fetched[: limits.max_rows]]
            return QueryResult(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                truncated=truncated,
                duration_ms=round(duration_ms, 2),
            )
        finally:
            conn.close()
