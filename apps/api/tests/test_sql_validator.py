"""Validation gate tests, including the adversarial safety regression."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.schema_catalog import SchemaCatalog
from app.domain.sql_validator import SqlValidator
from app.domain.validation import ValidationResult
from app.infra.sqlite_adapter import SqliteReadOnlyAdapter


@pytest.fixture
def validator(sample_db: Path) -> SqlValidator:
    db = sample_db
    catalog = SchemaCatalog.from_sqlite(db)
    adapter = SqliteReadOnlyAdapter(db)
    return SqlValidator(catalog, execute_check=adapter.explain)


def _codes(result: ValidationResult) -> set[str]:
    return {i.code for i in result.issues}


VALID = [
    "SELECT * FROM customers",
    "SELECT id, name FROM customers WHERE email LIKE '%@example.com'",
    "SELECT c.name, COUNT(*) FROM customers c "
    "JOIN orders o ON o.customer_id = c.id GROUP BY c.name",
    "SELECT SUM(quantity * unit_price * (1 - discount)) AS revenue FROM order_items",
    "SELECT c.name FROM customers c "
    "JOIN addresses a ON a.customer_id = c.id WHERE a.state = 'CA'",
    "SELECT p.name, AVG(r.rating) AS avg_rating FROM products p "
    "JOIN reviews r ON r.product_id = p.id GROUP BY p.name",
    # ORDER BY / HAVING on an output alias
    "SELECT carrier, AVG(delivered_at > promised_at) AS late_rate FROM shipments "
    "GROUP BY carrier HAVING late_rate > 0.05 ORDER BY late_rate DESC",
    # window functions
    "SELECT id, customer_id, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY placed_at) AS n "
    "FROM orders",
    "SELECT customer_id, placed_at, "
    "julianday(placed_at) - julianday(LAG(placed_at) OVER (PARTITION BY customer_id "
    "ORDER BY placed_at)) AS days_since_previous FROM orders",
    "SELECT name, NTILE(4) OVER (ORDER BY price) AS price_quartile FROM products",
    # recursive CTE over the category hierarchy
    "WITH RECURSIVE tree(id, name, depth) AS ("
    "SELECT id, name, 0 FROM categories WHERE parent_id IS NULL "
    "UNION ALL SELECT c.id, c.name, t.depth + 1 FROM categories c JOIN tree t ON c.parent_id = t.id"
    ") SELECT * FROM tree",
]


@pytest.mark.parametrize("sql", VALID)
def test_valid_queries_pass(validator: SqlValidator, sql: str) -> None:
    result = validator.validate(sql)
    assert result.passed, _codes(result)
    assert result.final_sql


FORBIDDEN = [
    "DROP TABLE customers",
    "DELETE FROM customers",
    "UPDATE customers SET email = 'x'",
    "INSERT INTO customers (id, name, email) VALUES (99, 'x', 'x@y.z')",
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
    # An unknown function not on the positive allowlist is rejected.
    result = validator.validate("SELECT made_up_fn(id) FROM customers")
    assert "UNSUPPORTED_FUNCTION" in _codes(result)


def test_dangerous_function_rejected(validator: SqlValidator) -> None:
    # Known-dangerous functions hit the hard denylist regardless of how they parse.
    result = validator.validate("SELECT load_extension('x') FROM customers")
    assert "FORBIDDEN_FUNCTION" in _codes(result)


def test_cartesian_join_rejected(validator: SqlValidator) -> None:
    assert "CARTESIAN_JOIN" in _codes(validator.validate("SELECT * FROM customers, orders"))


def test_parse_error_not_passed(validator: SqlValidator) -> None:
    assert not validator.validate("SELECT FROM WHERE").passed
