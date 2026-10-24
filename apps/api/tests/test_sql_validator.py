"""Validation gate tests, including the adversarial safety regression."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.db.build import build_sample_db
from app.domain.schema_catalog import SchemaCatalog
from app.domain.sql_validator import SqlValidator
from app.domain.validation import ValidationResult
from app.infra.sqlite_adapter import SqliteReadOnlyAdapter


@pytest.fixture
def validator(tmp_path: Path) -> SqlValidator:
    db = build_sample_db(tmp_path / "v.sqlite")
    catalog = SchemaCatalog.from_sqlite(db)
    adapter = SqliteReadOnlyAdapter(db)
    return SqlValidator(catalog, execute_check=adapter.explain)


def _codes(result: ValidationResult) -> set[str]:
    return {i.code for i in result.issues}


VALID = [
    "SELECT * FROM customers",
    "SELECT id, name FROM customers WHERE state = 'CA'",
    "SELECT c.name, COUNT(*) FROM customers c "
    "JOIN orders o ON o.customer_id = c.id GROUP BY c.name",
    "SELECT SUM(quantity * unit_price) AS revenue FROM order_items",
]


@pytest.mark.parametrize("sql", VALID)
def test_valid_queries_pass(validator: SqlValidator, sql: str) -> None:
    result = validator.validate(sql)
    assert result.passed, _codes(result)
    assert result.final_sql


FORBIDDEN = [
    "DROP TABLE customers",
    "DELETE FROM customers",
    "UPDATE customers SET state = 'CA'",
    "INSERT INTO customers (id, name) VALUES (99, 'x')",
    "ALTER TABLE customers ADD COLUMN x TEXT",
    "TRUNCATE TABLE customers",
    "CREATE TABLE t (id INTEGER)",
    "ATTACH DATABASE 'evil.db' AS evil",
    "PRAGMA table_info(customers)",
    "WITH x AS (SELECT 1) DELETE FROM customers",
]


@pytest.mark.parametrize("sql", FORBIDDEN)
def test_destructive_is_rejected(validator: SqlValidator, sql: str) -> None:
    result = validator.validate(sql)
    assert not result.passed
    assert "FORBIDDEN_OPERATION" in _codes(result)
    assert result.final_sql is None


def test_multi_statement_rejected(validator: SqlValidator) -> None:
    result = validator.validate("SELECT 1; DROP TABLE customers")
    assert "MULTI_STATEMENT" in _codes(result)


def test_unknown_table_rejected(validator: SqlValidator) -> None:
    assert "UNKNOWN_TABLE" in _codes(validator.validate("SELECT * FROM employees"))


def test_unknown_column_rejected(validator: SqlValidator) -> None:
    assert "UNKNOWN_COLUMN" in _codes(validator.validate("SELECT salary FROM customers"))


def test_unsupported_function_rejected(validator: SqlValidator) -> None:
    result = validator.validate("SELECT load_extension('x') FROM customers")
    assert "UNSUPPORTED_FUNCTION" in _codes(result)


def test_cartesian_join_rejected(validator: SqlValidator) -> None:
    assert "CARTESIAN_JOIN" in _codes(validator.validate("SELECT * FROM customers, orders"))


def test_parse_error_not_passed(validator: SqlValidator) -> None:
    assert not validator.validate("SELECT FROM WHERE").passed
