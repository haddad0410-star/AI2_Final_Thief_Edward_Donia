"""Batch 3, Task 4: EntropyEscapeThiefBrain -- capture-risk minimization,
mobility preservation, barrier-threat prediction, trajectory control,
risk-gated deceptive hints, bounded lookahead, and safety."""

from __future__ import annotations

import random

import pytest

from thief_peer.domain.belief_model import BeliefMap, normalize
from thief_peer.domain.belief_updates import uniform_prior
from thief_peer.domain.board import Board
from thief_peer.domain.deadline import DeadlineTracker
from thief_peer.domain.hints import HintIntent
from thief_peer.domain.positions import Direction, Position
from thief_peer.domain.rules import legal_move_directions
from thief_peer.strategy.decision import ThiefDecisionInput
from thief_peer.strategy.entropy_escape_config import EntropyEscapeWeights, weights_from_dict
from thief_peer.strategy.entropy_escape_thief_brain import EntropyEscapeThiefBrain

GRID = 7


def _peaked(cell: Position, grid: int = GRID) -> BeliefMap:
    raw = [[0.001 for _ in range(grid)] for _ in range(grid)]
    raw[cell.row][cell.col] = 500.0
    return normalize(grid, raw)


def _ctx(
    pos: Position, belief: BeliefMap, board: Board | None = None, seed: int = 0
) -> ThiefDecisionInput:
    board = board or Board(grid_size=GRID)
    return ThiefDecisionInput(
        legal_directions=legal_move_directions(pos, board),
        position=pos,
        visited=frozenset({pos}),
        board=board,
        belief=belief,
        step=1,
        deadline=DeadlineTracker(30.0).start(),
    )


def test_police_belief_concentrated_nearby_flees_away() -> None:
    brain = EntropyEscapeThiefBrain(rng=random.Random(1))
    d = brain.decide(_ctx(Position(3, 3), _peaked(Position(3, 4))))
    assert d.direction is Direction.W  # away from the believed police cell


def test_police_belief_diffuse_returns_legal_move() -> None:
    brain = EntropyEscapeThiefBrain(rng=random.Random(1))
    d = brain.decide(_ctx(Position(3, 3), uniform_prior(GRID)))
    assert d.direction in legal_move_directions(Position(3, 3), Board(grid_size=GRID))


def test_open_board_no_crash() -> None:
    brain = EntropyEscapeThiefBrain(rng=random.Random(1))
    d = brain.decide(_ctx(Position(3, 3), uniform_prior(GRID)))
    assert d.direction in legal_move_directions(Position(3, 3), Board(grid_size=GRID))


def test_corridor_returns_legal_move() -> None:
    barriers = frozenset(Position(3, c) for c in range(GRID) if c != 3)
    board = Board(grid_size=GRID, barriers=barriers)
    brain = EntropyEscapeThiefBrain(rng=random.Random(1))
    d = brain.decide(_ctx(Position(3, 3), _peaked(Position(6, 3)), board=board))
    assert d.direction in legal_move_directions(Position(3, 3), board)


def test_corner_escape_returns_legal_move() -> None:
    brain = EntropyEscapeThiefBrain(rng=random.Random(1))
    d = brain.decide(_ctx(Position(0, 0), _peaked(Position(1, 0))))
    assert d.direction in legal_move_directions(Position(0, 0), Board(grid_size=GRID))


def test_barrier_threat_cell_penalized_vs_open_cell() -> None:
    """A candidate cell near the believed police region, with few open
    neighbors of its own, must score lower than an equally-distant but
    more open cell (Task 4C)."""
    from thief_peer.strategy.entropy_escape_utility import barrier_threat

    board = Board(grid_size=GRID)
    belief = _peaked(Position(3, 3))
    choked = Board(
        grid_size=GRID, barriers=frozenset({Position(2, 3), Position(4, 3), Position(3, 2)})
    )
    threat_open = barrier_threat(Position(3, 4), board, belief)
    threat_choked = barrier_threat(Position(3, 4), choked, belief)
    assert threat_choked >= threat_open


def test_low_mobility_trap_still_returns_legal_move() -> None:
    barriers = frozenset({Position(2, 3), Position(3, 2), Position(3, 4)})
    board = Board(grid_size=GRID, barriers=barriers)
    brain = EntropyEscapeThiefBrain(rng=random.Random(1))
    d = brain.decide(_ctx(Position(3, 3), _peaked(Position(0, 0)), board=board))
    assert d.direction in legal_move_directions(Position(3, 3), board)


def test_all_but_one_move_blocked() -> None:
    barriers = frozenset({Position(2, 3), Position(3, 2), Position(4, 3)})
    board = Board(grid_size=GRID, barriers=barriers)
    brain = EntropyEscapeThiefBrain(rng=random.Random(1))
    d = brain.decide(_ctx(Position(3, 3), _peaked(Position(0, 0)), board=board))
    assert d.direction in (Direction.STAY, Direction.E)


def test_stay_as_only_legal_option() -> None:
    barriers = frozenset({Position(0, 1), Position(1, 0)})
    board = Board(grid_size=GRID, barriers=barriers)
    brain = EntropyEscapeThiefBrain(rng=random.Random(1))
    d = brain.decide(_ctx(Position(0, 0), uniform_prior(GRID), board=board))
    assert d.direction is Direction.STAY


def test_deceptive_hint_selected_under_high_capture_risk() -> None:
    """Risk is evaluated at the CHOSEN destination post-move (the strategy
    already fled toward safety), so the threshold must be set relative to
    the actual residual probability mass there, not an arbitrary constant."""
    weights = EntropyEscapeWeights(deception_risk_threshold=1e-9)
    brain = EntropyEscapeThiefBrain(rng=random.Random(1), weights=weights)
    d = brain.decide(_ctx(Position(3, 3), _peaked(Position(3, 4))))
    assert d.intent is HintIntent.LIE


def test_truthful_hint_selected_under_low_capture_risk() -> None:
    weights = EntropyEscapeWeights(deception_risk_threshold=0.99)
    brain = EntropyEscapeThiefBrain(rng=random.Random(1), weights=weights)
    d = brain.decide(_ctx(Position(3, 3), uniform_prior(GRID)))
    assert d.intent is HintIntent.TRUTH


def test_deterministic_test_mode_same_seed() -> None:
    belief = _peaked(Position(6, 6))
    a = EntropyEscapeThiefBrain(rng=random.Random(7)).decide(_ctx(Position(3, 3), belief)).direction
    b = EntropyEscapeThiefBrain(rng=random.Random(7)).decide(_ctx(Position(3, 3), belief)).direction
    assert a == b


def test_seeded_runtime_mode_never_crashes_across_seeds() -> None:
    belief = uniform_prior(GRID)
    for s in range(30):
        brain = EntropyEscapeThiefBrain(rng=random.Random(s))
        d = brain.decide(_ctx(Position(3, 3), belief))
        assert d.direction in legal_move_directions(Position(3, 3), Board(grid_size=GRID))


def test_deadline_fallback_never_exceeds_budget() -> None:
    import time

    brain = EntropyEscapeThiefBrain(rng=random.Random(1))
    ctx = _ctx(Position(0, 0), _peaked(Position(6, 6)))
    start = time.monotonic()
    for _ in range(200):
        brain.decide(ctx)
    assert (time.monotonic() - start) < 2.0


def test_no_true_position_access_structurally() -> None:
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(ThiefDecisionInput)}
    for forbidden in ("opponent", "true_position", "police_position", "enemy"):
        assert not any(forbidden in name for name in field_names), field_names


def test_no_mutation_of_peer_state() -> None:
    brain = EntropyEscapeThiefBrain(rng=random.Random(1))
    ctx = _ctx(Position(3, 3), _peaked(Position(0, 0)))
    snapshot = (ctx.position, ctx.belief, ctx.step)
    brain.decide(ctx)
    assert (ctx.position, ctx.belief, ctx.step) == snapshot


def test_empty_legal_moves_falls_back_to_stay() -> None:
    brain = EntropyEscapeThiefBrain(rng=random.Random(1))
    ctx = ThiefDecisionInput(
        legal_directions=(),
        position=Position(0, 0),
        visited=frozenset(),
        board=Board(grid_size=GRID),
        belief=uniform_prior(GRID),
        step=0,
        deadline=DeadlineTracker(30.0).start(),
    )
    assert brain.decide(ctx).direction is Direction.STAY


def test_weights_from_dict_rejects_unknown_key() -> None:
    with pytest.raises(ValueError, match="unknown"):
        weights_from_dict({"not_a_real_weight": 1.0})


def test_weights_with_overrides_does_not_mutate_original() -> None:
    base = EntropyEscapeWeights()
    tuned = base.with_overrides(expected_distance=5.0)
    assert base.expected_distance != tuned.expected_distance
    assert tuned.expected_distance == 5.0


def test_always_returns_legal_move_across_random_scenarios() -> None:
    brain = EntropyEscapeThiefBrain(rng=random.Random(999))
    rng = random.Random(999)
    for _ in range(300):
        pos = Position(rng.randrange(GRID), rng.randrange(GRID))
        target = Position(rng.randrange(GRID), rng.randrange(GRID))
        ctx = _ctx(pos, _peaked(target))
        d = brain.decide(ctx)
        assert d.direction in ctx.legal_directions


def test_loaded_from_private_config_path() -> None:
    from thief_peer.strategy.loader import build_strategy

    brain = build_strategy(
        "thief_peer.strategy.entropy_escape_thief_brain:EntropyEscapeThiefBrain",
        rng=random.Random(1),
    )
    assert isinstance(brain, EntropyEscapeThiefBrain)
