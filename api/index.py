"""Vercel serverless entrypoint.

Exposes the FastAPI ASGI app so Vercel's Python runtime can serve it. The backend package
lives under apps/api in this monorepo, so we add it to the path before importing. The sample
database is bundled read-only (see vercel.json includeFiles); the conversation DB is written to
/tmp (the only writable location on the serverless filesystem).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent / "apps" / "api"
sys.path.insert(0, str(_API_ROOT))

# Conversation history is per-instance and ephemeral on serverless (documented limitation).
os.environ.setdefault("APP_DB_DIR", "/tmp")

from app.main import app  # noqa: E402  — ASGI app served by Vercel

__all__ = ["app"]
