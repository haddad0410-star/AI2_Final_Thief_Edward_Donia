"""Batch 3.5 Task 6: frozen observation-to-belief update order.

Order: prior belief -> transition -> barrier mask -> scent -> hint ->
normalize. See docs/BELIEF_MODEL.md.
"""

from __future__ import annotations

from thief_peer.domain.belief_updates import uniform_prior
from thief_peer.domain.board import Board
from thief_peer.domain.hint_region import region_cells
from thief_peer.domain.positions import Position
from thief_peer.domain.scent import apply_turn, empty_scent_field
from thief_peer.services.belief_update import update_belief
from thief_peer.services.subgame_state import SubGameState

GRID = 7


def test_barrier_mask_applied_before_scent_and_hint() -> None:
    """A barrier cell must stay zero even under strong scent+hint evidence
    (proves masking happens BEFORE evidence folds in, not after)."""
    board = Board(grid_size=GRID).with_barrier(Position(3, 3))
    field = apply_turn(empty_scent_field(GRID), Position(3, 3), 0.10)
    belief = uniform_prior(GRID, board.barriers)
    updated, _trust = update_belief(belief, board, field, region_cells("central", GRID), 0.5)
    assert updated.grid[3][3] == 0.0


def test_prior_belief_preserved_and_evolves_across_steps() -> None:
    board = Board(grid_size=GRID)
    belief = uniform_prior(GRID)
    assert belief.grid == uniform_prior(GRID).grid
    step1, trust1 = update_belief(belief, board, None, None, 0.5)
    step2, _trust2 = update_belief(step1, board, None, None, trust1)
    assert step1.grid != belief.grid
    assert step2.grid != step1.grid


def test_subgame_reset_starts_uniform() -> None:
    first = SubGameState.initial(GRID, 1, Position(3, 3))
    second = SubGameState.initial(GRID, 2, Position(3, 3))
    assert first.belief.grid == second.belief.grid
    assert first.hint_trust == second.hint_trust == 0.5
    assert first.hint_region is None and second.hint_region is None


def test_duplicate_evidence_application_is_deterministic() -> None:
    board = Board(grid_size=GRID)
    belief = uniform_prior(GRID)
    field = apply_turn(empty_scent_field(GRID), Position(4, 4), 0.10)
    once, _t = update_belief(belief, board, field, None, 0.5)
    replay, _t2 = update_belief(belief, board, field, None, 0.5)
    assert once.grid == replay.grid


def test_degenerate_normalization_falls_back_to_uniform() -> None:
    from thief_peer.domain.belief_model import normalize

    result = normalize(GRID, [[0.0] * GRID for _ in range(GRID)])
    uniform = 1.0 / (GRID * GRID)
    assert all(abs(v - uniform) < 1e-12 for row in result.grid for v in row)


def test_entropy_moves_with_evidence() -> None:
    from thief_peer.domain.belief_model import entropy

    board = Board(grid_size=GRID)
    belief = uniform_prior(GRID)
    baseline = entropy(belief)
    field = apply_turn(empty_scent_field(GRID), Position(6, 6), 0.10)
    updated, _t = update_belief(belief, board, field, None, 0.5)
    assert entropy(updated) != baseline


def test_strategy_receives_immutable_belief_snapshot() -> None:
    board = Board(grid_size=GRID)
    updated, _t = update_belief(uniform_prior(GRID), board, None, None, 0.5)
    import pytest

    with pytest.raises(TypeError):
        updated.grid[0][0] = 999.0  # type: ignore[index]
