"""Load versioned prompt templates from the prompts/ directory (one file per prompt)."""

from __future__ import annotations

from functools import cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent / "prompts"


@cache
def load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
