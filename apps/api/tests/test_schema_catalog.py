from pathlib import Path

from app.db.build import build_sample_db
from app.domain.schema_catalog import SchemaCatalog


def _catalog(tmp_path: Path) -> SchemaCatalog:
    db = build_sample_db(tmp_path / "test.sqlite")
    return SchemaCatalog.from_sqlite(db)


def test_tables_discovered(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    assert set(catalog.table_names()) == {"customers", "products", "orders", "order_items"}


def test_columns_and_primary_key(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    customers = catalog.get_table("customers")
    assert customers is not None
    assert customers.primary_key == ("id",)
    assert catalog.has_column("customers", "state")
    assert catalog.has_column("CUSTOMERS", "STATE")  # case-insensitive
    assert not catalog.has_column("customers", "salary")


def test_foreign_keys(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    items = catalog.get_table("order_items")
    assert items is not None
    refs = {(fk.column, fk.ref_table, fk.ref_column) for fk in items.foreign_keys}
    assert ("order_id", "orders", "id") in refs
    assert ("product_id", "products", "id") in refs


def test_unknown_table_returns_none(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    assert catalog.get_table("employees") is None


def test_summary_and_version(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    summary = catalog.compact_summary()
    assert "customers(" in summary
    assert "FK order_items.order_id -> orders.id" in summary
    assert len(catalog.version()) == 16
