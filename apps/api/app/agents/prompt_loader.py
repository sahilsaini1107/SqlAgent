"""Load versioned prompt templates from the prompts/ directory (one file per prompt)."""

from __future__ import annotations

from functools import cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent / "prompts"


@cache
def load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def render_prompt(name: str, **values: str) -> str:
    """Load a prompt and substitute ``{key}`` placeholders by literal replacement.

    Deliberately not ``str.format``: the interpolated values (the schema summary) embed
    free-text table/column comments that may contain ``{`` or ``}`` — e.g. an allowed-value
    set — which would make ``str.format`` raise. Literal replacement is brace-safe.
    """
    text = load_prompt(name)
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text
