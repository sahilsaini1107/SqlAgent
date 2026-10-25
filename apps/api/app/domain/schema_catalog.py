"""Authorized schema catalog.

An immutable, server-owned view of the database structure introspected from SQLite. It is
the single source of truth the agent is allowed to reference: SQL generation is grounded in
it, and the validator (later milestone) checks every table/column against it. User input
never adds to or overrides this catalog.

Descriptions come from ``--`` comments inside each CREATE TABLE statement, which SQLite keeps
verbatim in ``sqlite_master``: a comment on the CREATE line describes the table, and a comment
after a column definition describes that column (allowed values, units, business rules).
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Column:
    name: str
    data_type: str
    nullable: bool
    primary_key: bool
    description: str | None = None


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
    description: str | None = None

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
        definitions = [
            (row["name"], row["sql"] or "")
            for row in conn.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        tables: list[Table] = []
        for name, create_sql in definitions:
            table_note, column_notes = _comments(create_sql)
            columns = tuple(
                Column(
                    name=row["name"],
                    data_type=(row["type"] or "").upper(),
                    nullable=not bool(row["notnull"]),
                    primary_key=bool(row["pk"]),
                    description=column_notes.get(row["name"].lower()),
                )
                for row in conn.execute(f'PRAGMA table_info("{_quote(name)}")')
            )
            foreign_keys = tuple(
                ForeignKey(column=row["from"], ref_table=row["table"], ref_column=row["to"])
                for row in conn.execute(f'PRAGMA foreign_key_list("{_quote(name)}")')
            )
            tables.append(
                Table(
                    name=name, columns=columns, foreign_keys=foreign_keys, description=table_note
                )
            )
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
        """Concise, LLM-facing schema description: names, types, keys, foreign keys, and the
        table/column descriptions (allowed values, units, business rules)."""
        lines: list[str] = []
        for table in self.tables:
            columns = ", ".join(
                f"{col.name} {col.data_type}"
                + ("" if col.nullable else " NOT NULL")
                + (" PK" if col.primary_key else "")
                for col in table.columns
            )
            note = f"  -- {table.description}" if table.description else ""
            lines.append(f"{table.name}({columns}){note}")
            for col in table.columns:
                if col.description:
                    lines.append(f"  {col.name}: {col.description}")
            for fk in table.foreign_keys:
                lines.append(f"  FK {table.name}.{fk.column} -> {fk.ref_table}.{fk.ref_column}")
        return "\n".join(lines)

    def version(self) -> str:
        """Stable short hash of the structure; used for cache keys and execution binding."""
        return hashlib.sha256(self.compact_summary().encode("utf-8")).hexdigest()[:16]


def _quote(identifier: str) -> str:
    """Escape embedded double quotes so a table name is safely interpolated into a PRAGMA
    (which doesn't accept bound parameters for the object name)."""
    return identifier.replace('"', '""')


_COLUMN_NAME = re.compile(r'^\s*"?(\w+)"?\s')
_TABLE_CONSTRAINTS = {"primary", "unique", "foreign", "check", "constraint"}


def _comments(create_sql: str) -> tuple[str | None, dict[str, str]]:
    """Extract the table comment and per-column comments from a CREATE TABLE statement."""
    table_note: str | None = None
    column_notes: dict[str, str] = {}
    for index, line in enumerate(create_sql.splitlines()):
        code, sep, comment = line.partition("--")
        comment = comment.strip()
        if not sep or not comment:
            continue
        if index == 0:
            table_note = comment
            continue
        match = _COLUMN_NAME.match(code)
        if match and match.group(1).lower() not in _TABLE_CONSTRAINTS:
            column_notes[match.group(1).lower()] = comment
    return table_note, column_notes
