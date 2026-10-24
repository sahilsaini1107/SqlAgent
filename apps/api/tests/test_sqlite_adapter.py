"""Read-only sandbox tests — proving writes and dangerous calls fail at the engine."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.db.build import build_sample_db
from app.domain.query_policy import QueryLimits
from app.infra.sqlite_adapter import SqliteReadOnlyAdapter


@pytest.fixture
def adapter(tmp_path: Path) -> SqliteReadOnlyAdapter:
    return SqliteReadOnlyAdapter(build_sample_db(tmp_path / "a.sqlite"))


def test_select_returns_rows(adapter: SqliteReadOnlyAdapter) -> None:
    result = adapter.execute_read_only("SELECT id, name FROM customers ORDER BY id", QueryLimits())
    assert result.columns == ["id", "name"]
    assert result.row_count == 8
    assert not result.truncated


def test_row_cap_truncates(adapter: SqliteReadOnlyAdapter) -> None:
    result = adapter.execute_read_only(
        "SELECT id FROM customers ORDER BY id", QueryLimits(max_rows=3)
    )
    assert result.row_count == 3
    assert result.truncated


def test_write_is_blocked(adapter: SqliteReadOnlyAdapter) -> None:
    with pytest.raises(sqlite3.Error):
        adapter.execute_read_only("UPDATE customers SET state = 'ZZ'", QueryLimits())


def test_attach_is_blocked(adapter: SqliteReadOnlyAdapter) -> None:
    with pytest.raises(sqlite3.Error):
        adapter.execute_read_only("ATTACH DATABASE 'x.db' AS y", QueryLimits())


def test_disallowed_function_is_blocked(adapter: SqliteReadOnlyAdapter) -> None:
    with pytest.raises(sqlite3.Error):
        adapter.execute_read_only("SELECT load_extension('x')", QueryLimits())


def test_explain_accepts_valid_and_rejects_invalid(adapter: SqliteReadOnlyAdapter) -> None:
    adapter.explain("SELECT * FROM customers")
    with pytest.raises(sqlite3.Error):
        adapter.explain("SELECT nope FROM customers")
