"""BaselineThiefBrain: a simple, honestly-weak evasive baseline (Phase 7).

Design (per strategy_proposals.md Section 2): move to the legal cell that
MAXIMIZES Manhattan distance from ``belief.most_likely()`` -- the single most
likely cell the opponent occupies -- mirroring the baseline police logic but
fleeing instead of pursuing. Ties are broken by preferring unvisited cells, then
greater immediate mobility, then an injected RNG (deterministic in tests, seeded
in league play). It never inspects the opponent's true position, never places a
barrier, never fabricates a claim, always returns a legal move, and always falls
back to the first legal move on any internal error or degenerate belief.
"""

from __future__ import annotations

import random

from thief_peer.domain.belief_model import most_likely
from thief_peer.domain.positions import Direction, Position, apply_direction
from thief_peer.domain.rules import legal_move_directions
from thief_peer.strategy.decision import Decision, ThiefDecisionInput


class BaselineThiefBrain:
    """A deterministic-given-(inputs, seed) evasive thief move selector."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng

    def decide(self, ctx: ThiefDecisionInput) -> Decision:
        """Return a legal evasive Decision, never raising (fallback on error)."""
        try:
            return self._decide(ctx)
        except Exception:  # noqa: BLE001 -- strategy must never crash the peer
            return self._fallback(ctx)

    @staticmethod
    def _fallback(ctx: ThiefDecisionInput) -> Decision:
        directions = ctx.legal_directions or (Direction.STAY,)
        return Decision(direction=directions[0])

    def _decide(self, ctx: ThiefDecisionInput) -> Decision:
        if not ctx.legal_directions:
            return Decision(direction=Direction.STAY)
        target = most_likely(ctx.belief)
        candidates = list(ctx.legal_directions)
        if self._rng is not None:
            self._rng.shuffle(candidates)
        best = max(candidates, key=lambda d: self._score(ctx, target, d))
        return Decision(direction=best)

    def _score(self, ctx: ThiefDecisionInput, target: Position, direction: Direction) -> tuple:
        """Higher is better: (distance from believed opponent, unvisited?,
        immediate mobility). Used as a total-order sort key over legal moves."""
        dest = apply_direction(ctx.position, direction)
        distance = abs(dest.row - target.row) + abs(dest.col - target.col)
        unvisited = 0 if dest in ctx.visited else 1
        mobility = len(legal_move_directions(dest, ctx.board))
        return (distance, unvisited, mobility)
