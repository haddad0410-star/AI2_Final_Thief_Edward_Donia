"""Batch 3.5 Task 7: prove the strategy actually receives the REAL
pipeline-produced belief (not a synthetic one built by hand) and that
differing real evidence can change its decision.
"""

from __future__ import annotations

import dataclasses
import random

from thief_peer.domain.belief_updates import uniform_prior
from thief_peer.domain.board import Board
from thief_peer.domain.deadline import DeadlineTracker
from thief_peer.domain.hint_region import region_cells
from thief_peer.domain.positions import Position
from thief_peer.domain.rules import legal_move_directions
from thief_peer.domain.scent import apply_turn, empty_scent_field
from thief_peer.services.belief_update import update_belief
from thief_peer.strategy.baseline_thief_brain import BaselineThiefBrain
from thief_peer.strategy.decision import ThiefDecisionInput
from thief_peer.strategy.entropy_escape_thief_brain import EntropyEscapeThiefBrain

GRID = 7
POSITION = Position(3, 3)


def _request(belief) -> ThiefDecisionInput:
    board = Board(grid_size=GRID)
    return ThiefDecisionInput(
        legal_directions=legal_move_directions(POSITION, board),
        position=POSITION,
        visited=frozenset({POSITION}),
        board=board,
        belief=belief,
        step=5,
        deadline=DeadlineTracker(5.0).start(),
    )


def test_two_pipelines_differing_only_in_scent_produce_different_beliefs() -> None:
    board = Board(grid_size=GRID)
    no_evidence, _t = update_belief(uniform_prior(GRID), board, None, None, 0.5)
    field = apply_turn(empty_scent_field(GRID), Position(6, 6), 0.10)
    with_evidence, _t2 = update_belief(uniform_prior(GRID), board, field, None, 0.5)
    assert no_evidence.grid != with_evidence.grid


def test_two_pipelines_differing_only_in_hint_produce_different_beliefs() -> None:
    board = Board(grid_size=GRID)
    no_evidence, _t = update_belief(uniform_prior(GRID), board, None, None, 0.5)
    with_hint, _t2 = update_belief(
        uniform_prior(GRID), board, None, region_cells("southern", GRID), 0.5
    )
    assert no_evidence.grid != with_hint.grid


def test_advanced_brain_escape_direction_changes_with_concentrated_police_belief() -> None:
    """A police belief concentrated adjacent to the thief on one side should
    change the escape direction relative to a belief concentrated on the
    opposite side."""
    board = Board(grid_size=GRID)
    brain = EntropyEscapeThiefBrain(rng=random.Random(0))

    belief_north = uniform_prior(GRID)
    belief_south = uniform_prior(GRID)
    for _ in range(3):
        field_n = apply_turn(empty_scent_field(GRID), Position(0, 3), 0.10)
        belief_north, _t = update_belief(belief_north, board, field_n, None, 0.5)
        field_s = apply_turn(empty_scent_field(GRID), Position(6, 3), 0.10)
        belief_south, _t2 = update_belief(belief_south, board, field_s, None, 0.5)

    decision_vs_north = brain.decide(_request(belief_north))
    decision_vs_south = brain.decide(_request(belief_south))
    assert decision_vs_north.direction != decision_vs_south.direction


def test_brain_does_not_receive_true_position_field() -> None:
    names = {f.name for f in dataclasses.fields(ThiefDecisionInput)}
    assert not any("true" in n or "police_position" in n for n in names)


def test_brain_cannot_mutate_local_peer_state() -> None:
    board = Board(grid_size=GRID)
    belief, _t = update_belief(uniform_prior(GRID), board, None, None, 0.5)
    request = _request(belief)
    brain = BaselineThiefBrain(rng=random.Random(0))
    brain.decide(request)
    assert not hasattr(request, "_subgame_state")
    assert request.belief.grid == belief.grid
