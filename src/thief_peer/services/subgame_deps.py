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
) -> SubGameDeps:
    """Assemble SubGameDeps with the baseline brain + template hints by default."""
    from thief_peer.strategy.baseline_thief_brain import BaselineThiefBrain
    from thief_peer.strategy.hint_templates import TemplateHintProvider

    rng = random.Random(seed)
    return SubGameDeps(
        config=config,
        brain=brain or BaselineThiefBrain(rng=rng),
        hint_provider=hint_provider or TemplateHintProvider(rng=random.Random(seed + 1)),
        gateway=gateway,
        game_uid=game_uid,
        config_sha256=config_sha256,
    )
