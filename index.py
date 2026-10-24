"""Vercel entrypoint.

Vercel's FastAPI preset looks for a ``FastAPI`` instance named ``app`` in a root-level
``index.py`` and routes every request to it. The backend package lives under ``apps/api`` in
this monorepo, so it is put on the path before importing.

On Vercel the filesystem is read-only except ``/tmp``: the sample query database is built
during the Vercel build and bundled read-only (see ``vercel.json``), conversations are written
to ``/tmp`` (per-instance and ephemeral), and the built frontend is served by the same app.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "apps" / "api"))

os.environ.setdefault("APP_DB_DIR", "/tmp")
os.environ.setdefault("WEB_DIST_DIR", str(_ROOT / "apps" / "web" / "dist"))

from app.main import app as api_app  # noqa: E402 — needs the path set up above

app: FastAPI = api_app
