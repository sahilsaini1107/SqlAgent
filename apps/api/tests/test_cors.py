"""CORS for a separately hosted frontend."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app

FRONTEND = "https://sql-agent.vercel.app"


def _preflight(client: TestClient, origin: str) -> dict[str, str]:
    resp = client.options(
        "/api/chat/stream",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    return dict(resp.headers)


def test_no_cors_headers_by_default() -> None:
    resp = TestClient(create_app()).get("/health", headers={"Origin": FRONTEND})
    assert "access-control-allow-origin" not in resp.headers


def test_configured_origin_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cors_origins", f"{FRONTEND}/, http://localhost:4173")
    client = TestClient(create_app())
    assert _preflight(client, FRONTEND).get("access-control-allow-origin") == FRONTEND
    resp = client.get("/health", headers={"Origin": FRONTEND})
    assert resp.headers["access-control-allow-origin"] == FRONTEND
    assert "access-control-allow-origin" not in _preflight(client, "https://evil.example")


def test_preview_origins_match_regex(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cors_origin_regex", r"https://sql-agent-[a-z0-9-]+\.vercel\.app")
    client = TestClient(create_app())
    preview = "https://sql-agent-git-feature-x.vercel.app"
    assert _preflight(client, preview).get("access-control-allow-origin") == preview
    assert "access-control-allow-origin" not in _preflight(client, "https://other.vercel.app")
