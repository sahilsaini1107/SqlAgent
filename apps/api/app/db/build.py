"""Build the sample SQLite database from data/schema.sql and data/seed.sql.

Run as a module to (re)generate the sample database:

    uv run python -m app.db.build

The generated file is git-ignored; it is always reproducible from the committed SQL.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config import settings


def build_sample_db(
    db_path: Path | None = None,
    *,
    schema_path: Path | None = None,
    seed_path: Path | None = None,
    overwrite: bool = True,
) -> Path:
    db_path = db_path or settings.sample_db_path
    schema_path = schema_path or settings.data_dir / "schema.sql"
    seed_path = seed_path or settings.data_dir / "seed.sql"

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if overwrite and db_path.exists():
        db_path.unlink()

    schema_sql = schema_path.read_text(encoding="utf-8")
    seed_sql = seed_path.read_text(encoding="utf-8")

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(schema_sql)
        conn.executescript(seed_sql)
        conn.commit()
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
