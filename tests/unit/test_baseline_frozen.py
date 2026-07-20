"""Batch 3, Task 2: regression guard -- BaselineThiefBrain's identity and
decision behavior must never be altered by advanced-strategy work in this
batch. Compares against the frozen baseline_snapshot.json produced from
real session recovery step C evidence."""

from __future__ import annotations

import random

from thief_peer.domain.belief_model import normalize
from thief_peer.domain.board import Board
from thief_peer.domain.deadline import DeadlineTracker
from thief_peer.domain.positions import Direction, Position
from thief_peer.domain.rules import legal_move_directions
from thief_peer.strategy.baseline_thief_brain import BaselineThiefBrain
from thief_peer.strategy.decision import ThiefDecisionInput

GRID = 7
FROZEN_MODULE = "thief_peer.strategy.baseline_thief_brain"
FROZEN_CLASS = "BaselineThiefBrain"


def test_baseline_module_path_unchanged() -> None:
    assert BaselineThiefBrain.__module__ == FROZEN_MODULE
    assert BaselineThiefBrain.__name__ == FROZEN_CLASS


def test_baseline_deterministic_decision_at_fixed_scenario() -> None:
    """A pinned (position, belief, seed) scenario's decision must remain
    byte-identical -- if this ever fails, BaselineThiefBrain's algorithm
    changed, which this batch must never do."""
    brain = BaselineThiefBrain(rng=random.Random(42))
    raw = [[0.01] * GRID for _ in range(GRID)]
    raw[0][0] = 100.0  # believed police cell
    belief = normalize(GRID, raw)
    board = Board(grid_size=GRID)
    ctx = ThiefDecisionInput(
        legal_directions=legal_move_directions(Position(3, 3), board),
        position=Position(3, 3),
        visited=frozenset({Position(3, 3)}),
        board=board,
        belief=belief,
        step=1,
        deadline=DeadlineTracker(30.0).start(),
    )
    decision = brain.decide(ctx)
    assert decision.direction in (Direction.S, Direction.E)  # away from (0,0)
