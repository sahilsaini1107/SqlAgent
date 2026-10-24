"""Per-node model routing tests.

The router maps each graph node to a model tier. These lock the free-tier tiering so a
node can't silently drift onto the wrong (or a retired) model: high-volume nodes stay on the
Flash-Lite default, core SQL work runs on the Flash tier.
"""

from __future__ import annotations

from app.agents.factory import default_router
from app.agents.model_router import ModelRouter
from app.config import settings


def test_unmapped_node_falls_through_to_default() -> None:
    router = ModelRouter(default_model="flash-lite", overrides={"generate": "flash"})
    assert router.model_for("classify") == "flash-lite"
    assert router.model_for("generate") == "flash"


def test_high_volume_nodes_use_the_flash_lite_default() -> None:
    router = default_router()
    for node in ("classify", "explain"):
        assert router.model_for(node) == settings.gemini_model


def test_core_sql_nodes_use_the_core_tier() -> None:
    router = default_router()
    for node in ("generate", "repair", "optimize"):
        assert router.model_for(node) == settings.gemini_model_core
