"""The strategy seam's input/output value objects (Batch 2 Phase 7).

``ThiefDecisionInput`` deliberately has NO field that could carry the opponent's
true position -- the brain sees only legal moves, its own state, its own belief
grid, the step number, and a deadline. ``Decision`` is what the brain returns: a
legal move direction plus the honest truth/lie intent for the (separately
generated) hint. The brain never produces hint text, barriers, or any
capture/win claim.
"""

from __future__ import annotations

from dataclasses import dataclass

from thief_peer.domain.belief_model import BeliefMap
from thief_peer.domain.board import Board
from thief_peer.domain.deadline import DeadlineTracker
from thief_peer.domain.hints import HintIntent
from thief_peer.domain.positions import Direction, Position


@dataclass(frozen=True, slots=True)
class ThiefDecisionInput:
    """Everything a thief brain is allowed to see for one move."""

    legal_directions: tuple[Direction, ...]
    position: Position
    visited: frozenset[Position]
    board: Board
    belief: BeliefMap
    step: int
    deadline: DeadlineTracker


@dataclass(frozen=True, slots=True)
class Decision:
    """One turn's chosen move plus the honest hint-intent flag."""

    direction: Direction
    intent: HintIntent = HintIntent.TRUTH

    def honest(self) -> bool:
        return self.intent is HintIntent.TRUTH
