"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.db.build import build_sample_db


@pytest.fixture(scope="session")
def sample_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The generated sample database, built once per test run. Tests only ever read it."""
    return build_sample_db(tmp_path_factory.mktemp("data") / "sample.sqlite")
