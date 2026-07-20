"""SubGameDeps: everything one sub-game turn needs, gathered once (split out
of subgame_runtime.py to keep both files under the 150-meaningful-line cap).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime

from thief_peer.services.gateway import OpponentGateway
from thief_peer.shared.config_models import SharedGameConfig


@dataclass
class SubGameDeps:
    """Everything one sub-game turn needs, gathered once."""

    config: SharedGameConfig
    brain: object
    hint_provider: object
    gateway: OpponentGateway
    game_uid: str
    config_sha256: str

    @property
    def response_timeout(self) -> float:
        return float(self.config.network_and_league.response_timeout_sec)

    @property
    def survival_threshold(self) -> int:
        return self.config.movement_and_barriers.survival_threshold

    def now_iso(self) -> str:
        return datetime.now(UTC).isoformat()


def make_deps(
    config: SharedGameConfig,
    gateway: OpponentGateway,
    game_uid: str,
    config_sha256: str,
    *,
    brain: object | None = None,
    hint_provider: object | None = None,
    seed: int = 0,
    strategy_class: str | None = None,
    strategy_weights: dict | None = None,
) -> SubGameDeps:
    """Assemble SubGameDeps. If ``brain`` is not injected directly, the real
    private-config strategy selection (Batch 3, Task 5) is used --
    ``strategy_class`` defaults to the baseline thief brain when omitted, so
    every pre-existing caller that never passed it keeps identical
    behavior."""
    from thief_peer.strategy.hint_templates import TemplateHintProvider
    from thief_peer.strategy.loader import build_strategy

    rng = random.Random(seed)
    resolved_class = strategy_class or "thief_peer.strategy.baseline_thief_brain:BaselineThiefBrain"
    weights = None
    if strategy_weights:
        from thief_peer.strategy.entropy_escape_config import weights_from_dict

        weights = weights_from_dict(strategy_weights)
    return SubGameDeps(
        config=config,
        brain=brain or build_strategy(resolved_class, rng=rng, weights=weights),
        hint_provider=hint_provider or TemplateHintProvider(rng=random.Random(seed + 1)),
        gateway=gateway,
        game_uid=game_uid,
        config_sha256=config_sha256,
    )
