"""Integrity checks on the generated sample database.

The agent's answers are only as trustworthy as the data they run against, so these pin the
invariants the schema comments promise (money arithmetic, status timelines, foreign keys).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.db.seed import N_CUSTOMERS, N_ORDERS, generate


@pytest.fixture
def conn(sample_db: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(f"file:{sample_db}?mode=ro", uri=True)
    yield connection
    connection.close()


def _scalar(conn: sqlite3.Connection, sql: str) -> object:
    return conn.execute(sql).fetchone()[0]


def test_volumes(conn: sqlite3.Connection) -> None:
    assert _scalar(conn, "SELECT COUNT(*) FROM customers") == N_CUSTOMERS
    assert _scalar(conn, "SELECT COUNT(*) FROM orders") == N_ORDERS
    assert _scalar(conn, "SELECT COUNT(*) FROM order_items") > N_ORDERS


def test_foreign_keys_hold(conn: sqlite3.Connection) -> None:
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_order_money_adds_up(conn: sqlite3.Connection) -> None:
    bad_total = _scalar(conn, """
        SELECT COUNT(*) FROM orders
        WHERE ABS(total - (subtotal - discount_total + shipping_fee + tax_total)) > 0.011
    """)
    bad_subtotal = _scalar(conn, """
        SELECT COUNT(*) FROM orders o
        JOIN (SELECT order_id, ROUND(SUM(quantity * unit_price * (1 - discount)), 2) AS net
              FROM order_items GROUP BY order_id) l ON l.order_id = o.id
        WHERE ABS(o.subtotal - l.net) > 0.011
    """)
    assert bad_total == 0
    assert bad_subtotal == 0


def test_status_matches_latest_history(conn: sqlite3.Connection) -> None:
    mismatched = _scalar(conn, """
        SELECT COUNT(*) FROM orders o
        WHERE o.status <> (SELECT h.status FROM order_status_history h
                           WHERE h.order_id = o.id ORDER BY h.changed_at DESC, h.id DESC LIMIT 1)
    """)
    assert mismatched == 0


def test_timelines_are_ordered(conn: sqlite3.Connection) -> None:
    assert _scalar(conn, """
        SELECT COUNT(*) FROM orders o JOIN customers c ON c.id = o.customer_id
        WHERE o.placed_at < c.created_at
    """) == 0
    assert _scalar(conn, """
        SELECT COUNT(*) FROM shipments s JOIN orders o ON o.id = s.order_id
        WHERE s.shipped_at < o.placed_at OR s.delivered_at < s.shipped_at
    """) == 0
    assert _scalar(conn, """
        SELECT COUNT(*) FROM shipments s JOIN orders o ON o.id = s.order_id
        WHERE o.status IN ('pending', 'paid', 'cancelled')
    """) == 0


def test_every_currency_month_has_a_rate(conn: sqlite3.Connection) -> None:
    missing = _scalar(conn, """
        SELECT COUNT(*) FROM orders o
        LEFT JOIN exchange_rates fx
          ON fx.currency = o.currency AND fx.rate_date = strftime('%Y-%m-01', o.placed_at)
        WHERE fx.rate_to_usd IS NULL
    """)
    assert missing == 0


def test_one_open_price_per_product(conn: sqlite3.Connection) -> None:
    assert _scalar(conn, """
        SELECT COUNT(*) FROM products p
        WHERE (SELECT COUNT(*) FROM product_price_history h
               WHERE h.product_id = p.id AND h.valid_to IS NULL) <> 1
           OR p.price <> (SELECT h.price FROM product_price_history h
                          WHERE h.product_id = p.id AND h.valid_to IS NULL)
    """) == 0


def test_generation_is_deterministic() -> None:
    first, second = generate(), generate()
    for table in ("orders", "order_items", "payments", "support_tickets"):
        assert first[table] == second[table], table
