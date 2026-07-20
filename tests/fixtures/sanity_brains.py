"""Batch 3.5 Task 9: deterministic, SCRIPTED brains for capture/barrier
sanity fixtures only -- never used in league play, never part of the
shipped strategy set. Move selection is still pure Python; no LLM, no
network.
"""

from __future__ import annotations

from thief_peer.domain.positions import Direction
from thief_peer.strategy.decision import Decision, ThiefDecisionInput


class StationaryThiefBrain:
    """Always STAYs if legal, else the first legal direction -- used only to
    make capture/barrier-trap sanity scenarios deterministic and bounded."""

    def __init__(self, rng: object | None = None) -> None:
        del rng  # accepted only for loader compatibility (build_strategy always passes it)

    def decide(self, ctx: ThiefDecisionInput) -> Decision:
        if Direction.STAY in ctx.legal_directions:
            return Decision(direction=Direction.STAY)
        directions = ctx.legal_directions or (Direction.STAY,)
        return Decision(direction=directions[0])
