"""Conversation persistence.

A small SQLite-backed store for conversations and their messages — kept separate from the
sample *query* database. It provides the transcript for the history endpoint and the last
validated SQL used to ground follow-up requests.
"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id         TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role            TEXT NOT NULL,
    content         TEXT,
    sql             TEXT,
    status          TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id);
"""


class SessionStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def create_conversation(self) -> str:
        conversation_id = uuid.uuid4().hex
        with closing(self._connect()) as conn, conn:
            conn.execute("INSERT INTO conversations (id) VALUES (?)", (conversation_id,))
        return conversation_id

    def conversation_exists(self, conversation_id: str) -> bool:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
        return row is not None

    def add_message(
        self,
        conversation_id: str,
        role: str,
        *,
        content: str | None = None,
        sql: str | None = None,
        status: str | None = None,
    ) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content, sql, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (conversation_id, role, content, sql, status),
            )

    def add_turn(
        self,
        conversation_id: str,
        *,
        user_content: str,
        assistant_content: str | None,
        assistant_sql: str | None,
        assistant_status: str | None,
    ) -> None:
        """Persist the user message and the assistant reply in a single transaction, so a
        failure mid-turn can never leave an orphaned user message without its response."""
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'user', ?)",
                (conversation_id, user_content),
            )
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content, sql, status) "
                "VALUES (?, 'assistant', ?, ?, ?)",
                (conversation_id, assistant_content, assistant_sql, assistant_status),
            )

    def last_validated_sql(self, conversation_id: str) -> str | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT sql FROM messages "
                "WHERE conversation_id = ? AND sql IS NOT NULL "
                "AND status IN ('validated', 'executed') "
                "ORDER BY id DESC LIMIT 1",
                (conversation_id,),
            ).fetchone()
        return row["sql"] if row else None

    def get_history(self, conversation_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT role, content, sql, status, created_at FROM messages "
                "WHERE conversation_id = ? ORDER BY id",
                (conversation_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_conversation(self, conversation_id: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
