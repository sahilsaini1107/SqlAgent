from __future__ import annotations

from pathlib import Path

from app.infra.session_store import SessionStore


def test_roundtrip(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "s.sqlite")
    cid = store.create_conversation()
    assert store.conversation_exists(cid)

    store.add_message(cid, "user", content="show customers")
    store.add_message(cid, "assistant", content="ok", sql="SELECT 1", status="validated")

    assert store.last_validated_sql(cid) == "SELECT 1"
    history = store.get_history(cid)
    assert [m["role"] for m in history] == ["user", "assistant"]

    store.delete_conversation(cid)
    assert not store.conversation_exists(cid)
    assert store.get_history(cid) == []


def test_last_validated_ignores_failed(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "s.sqlite")
    cid = store.create_conversation()
    store.add_message(cid, "assistant", content="x", sql="SELECT bad", status="validation_failed")
    assert store.last_validated_sql(cid) is None
