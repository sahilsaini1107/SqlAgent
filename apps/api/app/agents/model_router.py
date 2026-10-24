"""Node-to-model routing.

The single seam that maps a graph node to a model id. Today every node resolves to the one
configured model (one key, one model); switching to per-node tiers (e.g. a cheaper model for
classification, a stronger one for generation) is a matter of populating ``overrides`` from
config — no node code changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelRouter:
    default_model: str
    overrides: dict[str, str] = field(default_factory=dict)

    def model_for(self, node: str) -> str:
        return self.overrides.get(node, self.default_model)
