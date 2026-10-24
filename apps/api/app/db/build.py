"""Build the sample SQLite database from data/schema.sql and the deterministic seeder.

Run as a module to (re)generate the sample database:

    uv run python -m app.db.build

The generated file is git-ignored; it is always reproducible from the committed schema and
the fixed-seed generator in app.db.seed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config import settings
from app.db.seed import seed_database


def build_sample_db(
    db_path: Path | None = None,
    *,
    schema_path: Path | None = None,
    overwrite: bool = True,
) -> Path:
    db_path = db_path or settings.sample_db_path
    schema_path = schema_path or settings.data_dir / "schema.sql"

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if overwrite and db_path.exists():
        db_path.unlink()

    schema_sql = schema_path.read_text(encoding="utf-8")

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(schema_sql)
        seed_database(conn)
        _verify_foreign_keys(conn)
    finally:
        conn.close()
    return db_path


def _verify_foreign_keys(conn: sqlite3.Connection) -> None:
    violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
    if violations:
        raise ValueError(f"seed data violates foreign keys: {violations}")


if __name__ == "__main__":
    path = build_sample_db()
    print(f"Built sample database at {path}")
