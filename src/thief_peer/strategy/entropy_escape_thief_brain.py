"""EntropyEscapeThiefBrain: original advanced Thief strategy (Batch 3,
Task 4). See docs/STRATEGY.md for the full documented design and utility
formula.

Uses the complete belief distribution about the police's likely location
(not just its argmax), a bounded belief-transition lookahead, mobility/
reachable-region preservation, a structural barrier-threat proxy, a
trajectory-predictability penalty, and risk-gated deceptive hint selection.
Never accesses -- and structurally cannot access, per
``ThiefDecisionInput``'s field set -- the opponent's true position.
"""

from __future__ import annotations

import random
from collections import deque

from thief_peer.domain.hints import HintIntent
from thief_peer.domain.positions import Direction, apply_direction
from thief_peer.strategy.decision import Decision, ThiefDecisionInput
from thief_peer.strategy.entropy_escape_config import DEFAULT_WEIGHTS, EntropyEscapeWeights
from thief_peer.strategy.entropy_escape_utility import (
    capture_risk,
    project_belief,
    score_move,
)

_HISTORY_LEN = 4


class EntropyEscapeThiefBrain:
    """Risk-aware evasion with bounded lookahead, mobility preservation,
    and risk-gated deceptive hints."""

    def __init__(
        self, rng: random.Random | None = None, weights: EntropyEscapeWeights | None = None
    ) -> None:
        self._rng = rng or random.Random()
        self._weights = weights or DEFAULT_WEIGHTS
        self._recent_directions: deque[Direction] = deque(maxlen=_HISTORY_LEN)

    def decide(self, ctx: ThiefDecisionInput) -> Decision:
        """Return a legal, risk-aware evasive Decision; never raises."""
        try:
            decision = self._decide(ctx)
        except Exception:  # noqa: BLE001 -- strategy must never crash the peer
            decision = self._fallback(ctx)
        self._recent_directions.append(decision.direction)
        return decision

    @staticmethod
    def _fallback(ctx: ThiefDecisionInput) -> Decision:
        directions = ctx.legal_directions or (Direction.STAY,)
        return Decision(direction=directions[0])

    def _decide(self, ctx: ThiefDecisionInput) -> Decision:
        if not ctx.legal_directions:
            return Decision(direction=Direction.STAY)
        w = self._weights
        projected = project_belief(ctx.belief, ctx.board, w.lookahead_depth)
        recent = tuple(self._recent_directions)

        best_direction = ctx.legal_directions[0]
        best_score = float("-inf")
        for direction in ctx.legal_directions:
            destination = apply_direction(ctx.position, direction)
            s = score_move(
                origin=ctx.position,
                destination=destination,
                belief=ctx.belief,
                projected_belief=projected,
                board=ctx.board,
                visited=ctx.visited,
                recent_directions=recent,
                weights=w,
            )
            if self._rng is not None:
                s += self._rng.random() * 1e-9  # break exact ties without biasing order
            if s > best_score:
                best_score, best_direction = s, direction

        destination = apply_direction(ctx.position, best_direction)
        risk = capture_risk(destination, ctx.belief)
        intent = HintIntent.LIE if risk >= w.deception_risk_threshold else HintIntent.TRUTH
        return Decision(direction=best_direction, intent=intent)
