from pathlib import Path

import pytest

from app.domain.schema_catalog import SchemaCatalog

CORE_TABLES = {
    "categories", "brands", "suppliers", "products", "product_price_history",
    "product_variants", "warehouses", "inventory", "purchase_orders", "purchase_order_items",
    "marketing_campaigns", "customers", "addresses", "coupons", "orders", "order_items",
    "order_status_history", "order_coupons", "payments", "shipments", "returns",
    "return_items", "carts", "cart_items", "wishlist_items", "reviews", "support_tickets",
    "exchange_rates",
}


@pytest.fixture
def catalog(sample_db: Path) -> SchemaCatalog:
    return SchemaCatalog.from_sqlite(sample_db)


def test_tables_discovered(catalog: SchemaCatalog) -> None:
    assert set(catalog.table_names()) == CORE_TABLES


def test_columns_and_primary_key(catalog: SchemaCatalog) -> None:
    customers = catalog.get_table("customers")
    assert customers is not None
    assert customers.primary_key == ("id",)
    assert catalog.has_column("customers", "email")
    assert catalog.has_column("CUSTOMERS", "EMAIL")  # case-insensitive
    assert not catalog.has_column("customers", "salary")
    assert catalog.has_column("addresses", "state")


def test_composite_primary_key(catalog: SchemaCatalog) -> None:
    order_coupons = catalog.get_table("order_coupons")
    assert order_coupons is not None
    assert set(order_coupons.primary_key) == {"order_id", "coupon_id"}
    rates = catalog.get_table("exchange_rates")
    assert rates is not None
    assert set(rates.primary_key) == {"currency", "rate_date"}


def test_foreign_keys(catalog: SchemaCatalog) -> None:
    items = catalog.get_table("order_items")
    assert items is not None
    refs = {(fk.column, fk.ref_table, fk.ref_column) for fk in items.foreign_keys}
    assert ("order_id", "orders", "id") in refs
    assert ("variant_id", "product_variants", "id") in refs


def test_self_referential_foreign_keys(catalog: SchemaCatalog) -> None:
    for table, column in (("categories", "parent_id"), ("customers", "referred_by_id")):
        found = catalog.get_table(table)
        assert found is not None
        assert (column, table) in {(fk.column, fk.ref_table) for fk in found.foreign_keys}


def test_unknown_table_returns_none(catalog: SchemaCatalog) -> None:
    assert catalog.get_table("employees") is None


def test_descriptions_come_from_schema_comments(catalog: SchemaCatalog) -> None:
    orders = catalog.get_table("orders")
    assert orders is not None
    assert orders.description and "orders.currency" in orders.description
    status = orders.column("status")
    assert status is not None and status.description
    assert "delivered" in status.description
    # Columns without a comment have no description.
    customer_id = orders.column("customer_id")
    assert customer_id is not None and customer_id.description is None


def test_summary_and_version(catalog: SchemaCatalog) -> None:
    summary = catalog.compact_summary()
    assert "customers(" in summary
    assert "FK order_items.order_id -> orders.id" in summary
    assert "  status: current status: pending|paid|" in summary
    assert len(catalog.version()) == 16
