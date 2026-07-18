"""Phase 7: BaselineThiefBrain -- always-legal moves, determinism, seeded
reproducibility, degenerate fallback, no opponent-position access, deadline
compliance, and dynamic strategy loading from the private config reference."""

from __future__ import annotations

import dataclasses
import random
import time

from thief_peer.domain.belief_model import BeliefMap, normalize
from thief_peer.domain.belief_updates import uniform_prior
from thief_peer.domain.board import Board
from thief_peer.domain.deadline import DeadlineTracker
from thief_peer.domain.positions import Position, apply_direction
from thief_peer.domain.rules import legal_move_directions
from thief_peer.strategy.baseline_thief_brain import BaselineThiefBrain
from thief_peer.strategy.decision import Decision, ThiefDecisionInput
from thief_peer.strategy.loader import StrategyLoadError, build_strategy, load_strategy_class

GRID = 7
STRAT_REF = "thief_peer.strategy.baseline_thief_brain:BaselineThiefBrain"


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


def test_always_returns_a_legal_move_over_random_boards() -> None:
    rng = random.Random(1234)
    brain = BaselineThiefBrain(rng=random.Random(1))
    for _ in range(500):
        pos = Position(rng.randrange(GRID), rng.randrange(GRID))
        barriers = frozenset(
            Position(rng.randrange(GRID), rng.randrange(GRID)) for _ in range(rng.randrange(5))
        ) - {pos}
        board = Board(grid_size=GRID, barriers=barriers)
        raw = [[rng.random() for _ in range(GRID)] for _ in range(GRID)]
        belief = normalize(GRID, raw)
        ctx = _ctx(pos, belief, board)
        decision = brain.decide(ctx)
        assert decision.direction in ctx.legal_directions
        dest = apply_direction(pos, decision.direction)
        assert board.is_in_bounds(dest) and not board.is_barrier(dest)


def test_moves_away_from_believed_opponent() -> None:
    brain = BaselineThiefBrain()
    board = Board(grid_size=GRID)
    # Opponent believed at top-left corner; thief at center should flee toward
    # higher row/col (S or E increase Manhattan distance from (0,0)).
    raw = [[0.0] * GRID for _ in range(GRID)]
    raw[0][0] = 1.0
    belief = normalize(GRID, raw)
    ctx = _ctx(Position(3, 3), belief, board)
    dest = apply_direction(ctx.position, brain.decide(ctx).direction)
    assert (abs(dest.row) + abs(dest.col)) >= (3 + 3)  # never moves closer to (0,0)


def test_deterministic_without_rng() -> None:
    brain = BaselineThiefBrain()
    belief = uniform_prior(GRID)
    ctx = _ctx(Position(3, 3), belief)
    first = brain.decide(ctx).direction
    for _ in range(10):
        assert brain.decide(ctx).direction is first


def test_seeded_reproducibility() -> None:
    belief = uniform_prior(GRID)
    ctx = _ctx(Position(3, 3), belief)
    a = BaselineThiefBrain(rng=random.Random(5678)).decide(ctx).direction
    b = BaselineThiefBrain(rng=random.Random(5678)).decide(ctx).direction
    assert a is b  # same seed -> same tie-break


def test_fallback_on_degenerate_belief_does_not_crash() -> None:
    brain = BaselineThiefBrain()
    # All-zero raw grid -> normalize() yields uniform; still must return legal.
    belief = normalize(GRID, [[0.0] * GRID for _ in range(GRID)])
    ctx = _ctx(Position(0, 0), belief)
    assert brain.decide(ctx).direction in ctx.legal_directions


def test_decision_input_has_no_opponent_position_field() -> None:
    names = {f.name for f in dataclasses.fields(ThiefDecisionInput)}
    for forbidden in ("opponent", "true_position", "enemy", "police_position"):
        assert not any(forbidden in n for n in names), names


def test_decide_signature_takes_only_context() -> None:
    import inspect

    params = list(inspect.signature(BaselineThiefBrain.decide).parameters)
    assert params == ["self", "ctx"]  # no separate true-position argument


def test_deadline_compliance_is_fast() -> None:
    brain = BaselineThiefBrain(rng=random.Random(1))
    belief = uniform_prior(GRID)
    ctx = _ctx(Position(3, 3), belief)
    start = time.monotonic()
    for _ in range(1000):
        brain.decide(ctx)
    assert (time.monotonic() - start) < 1.0  # 1000 decisions well under a second


def test_returns_decision_type() -> None:
    brain = BaselineThiefBrain()
    out = brain.decide(_ctx(Position(3, 3), uniform_prior(GRID)))
    assert isinstance(out, Decision)
    assert out.honest() is True  # baseline is honest by default


def test_strategy_loaded_from_reference() -> None:
    cls = load_strategy_class(STRAT_REF)
    assert cls is BaselineThiefBrain
    brain = build_strategy(STRAT_REF, rng=random.Random(1))
    assert isinstance(brain, BaselineThiefBrain)


def test_strategy_loader_rejects_bad_reference() -> None:
    for bad in ("no_colon_here", "thief_peer.strategy.loader:DoesNotExist", "no.module.here:X"):
        try:
            load_strategy_class(bad)
            raise AssertionError(f"expected StrategyLoadError for {bad!r}")
        except StrategyLoadError:
            pass
