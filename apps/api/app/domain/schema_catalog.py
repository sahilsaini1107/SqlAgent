"""Authorized schema catalog.

An immutable, server-owned view of the database structure introspected from SQLite. It is
the single source of truth the agent is allowed to reference: SQL generation is grounded in
it, and the validator (later milestone) checks every table/column against it. User input
never adds to or overrides this catalog.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Column:
    name: str
    data_type: str
    nullable: bool
    primary_key: bool


@dataclass(frozen=True)
class ForeignKey:
    column: str
    ref_table: str
    ref_column: str


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...]
    foreign_keys: tuple[ForeignKey, ...]

    @property
    def primary_key(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns if c.primary_key)

    def column(self, name: str) -> Column | None:
        lowered = name.lower()
        return next((c for c in self.columns if c.name.lower() == lowered), None)


@dataclass(frozen=True)
class SchemaCatalog:
    tables: tuple[Table, ...]

    @classmethod
    def from_sqlite(cls, db_path: Path) -> SchemaCatalog:
        """Introspect a database opened read-only."""
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            return cls._introspect(conn)
        finally:
            conn.close()

    @classmethod
    def _introspect(cls, conn: sqlite3.Connection) -> SchemaCatalog:
        conn.row_factory = sqlite3.Row
        table_names = [
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        tables: list[Table] = []
        for name in table_names:
            columns = tuple(
                Column(
                    name=row["name"],
                    data_type=(row["type"] or "").upper(),
                    nullable=not bool(row["notnull"]),
                    primary_key=bool(row["pk"]),
                )
                for row in conn.execute(f'PRAGMA table_info("{name}")')
            )
            foreign_keys = tuple(
                ForeignKey(column=row["from"], ref_table=row["table"], ref_column=row["to"])
                for row in conn.execute(f'PRAGMA foreign_key_list("{name}")')
            )
            tables.append(Table(name=name, columns=columns, foreign_keys=foreign_keys))
        return cls(tables=tuple(tables))

    def table_names(self) -> tuple[str, ...]:
        return tuple(t.name for t in self.tables)

    def get_table(self, name: str) -> Table | None:
        lowered = name.lower()
        return next((t for t in self.tables if t.name.lower() == lowered), None)

    def has_column(self, table: str, column: str) -> bool:
        found = self.get_table(table)
        return found is not None and found.column(column) is not None

    def compact_summary(self) -> str:
        """Concise, LLM-facing schema description (names, types, keys, foreign keys)."""
        lines: list[str] = []
        for table in self.tables:
            columns = ", ".join(
                f"{col.name} {col.data_type}"
                + ("" if col.nullable else " NOT NULL")
                + (" PK" if col.primary_key else "")
                for col in table.columns
            )
            lines.append(f"{table.name}({columns})")
            for fk in table.foreign_keys:
                lines.append(f"  FK {table.name}.{fk.column} -> {fk.ref_table}.{fk.ref_column}")
        return "\n".join(lines)

    def version(self) -> str:
        """Stable short hash of the structure; used for cache keys and execution binding."""
        return hashlib.sha256(self.compact_summary().encode("utf-8")).hexdigest()[:16]
