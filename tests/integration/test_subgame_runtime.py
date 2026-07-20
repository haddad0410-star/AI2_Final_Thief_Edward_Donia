"""Phase 9: single sub-game runtime against an in-process FAKE opponent gateway
(mocks are test-only). Covers survival, capture resolution, and technical loss."""

from __future__ import annotations

import asyncio
import dataclasses

import pytest
from _thief_series_fixtures import CFG_SHA, CONFIG, BlockingGateway, FakeGateway

from thief_peer.domain.captures import SubGameResult
from thief_peer.domain.state_machine import EventKind, PeerState, TransitionEvent
from thief_peer.services.subgame_runtime import SubGameRuntime, make_deps
from thief_peer.services.subgame_state import SubGameState


def _run(runtime: SubGameRuntime, **kw):
    return asyncio.run(runtime.run(**kw))


def test_survival_happy_path() -> None:
    deps = make_deps(CONFIG, FakeGateway(), "uid-s", CFG_SHA, seed=7)
    result = _run(SubGameRuntime(deps))
    assert result.result is SubGameResult.SURVIVAL
    assert result.steps_taken == CONFIG.movement_and_barriers.survival_threshold
    assert result.thief_score == CONFIG.scoring.survival_thief
    assert result.audit is not None and result.audit.verified


def test_capture_resolution_on_matching_claim() -> None:
    # Police claims the thief's start cell (3,3) on the very first reveal.
    # The honest confirmation cannot be delivered until the FOLLOWING turn's
    # reveal (the synchronous per-step exchange structurally cannot answer a
    # same-step claim -- see turn_loop.py's ``was_confirming_prior_capture``
    # handling, Batch 3.5 Task 4/9 defect H fix), so this now takes 2 turns:
    # one to detect+acknowledge the claim, one to deliver the confirmation.
    gw = FakeGateway(opponent_turn={"capture_claim": [3, 3]})
    deps = make_deps(CONFIG, gw, "uid-c", CFG_SHA, seed=1)
    result = _run(SubGameRuntime(deps))
    assert result.result is SubGameResult.CAPTURE
    assert result.thief_score == CONFIG.scoring.capture_thief
    assert result.steps_taken == 2


def test_barrier_on_thief_cell_is_capture() -> None:
    gw = FakeGateway(opponent_turn={"barrier_placed": [3, 3]})
    deps = make_deps(CONFIG, gw, "uid-b", CFG_SHA, seed=1)
    result = _run(SubGameRuntime(deps))
    assert result.result is SubGameResult.CAPTURE


def test_technical_loss_on_malformed_opponent() -> None:
    deps = make_deps(CONFIG, FakeGateway(reject=True), "uid-t", CFG_SHA, seed=1)
    result = _run(SubGameRuntime(deps))
    assert result.result is SubGameResult.TECHNICAL_LOSS
    assert result.technical_loss is True
    assert "technical loss" in result.reason


def test_runtime_state_has_no_opponent_true_position_field() -> None:
    names = {f.name for f in dataclasses.fields(SubGameState)}
    for forbidden in ("opponent_position", "opponent_true", "true_position", "police_position"):
        assert not any(forbidden in n for n in names), names


def test_records_are_sealed_and_ordered() -> None:
    deps = make_deps(CONFIG, FakeGateway(), "uid-o", CFG_SHA, seed=3)
    result = _run(SubGameRuntime(deps), max_turns=5)
    steps = [r.payload.step for r in result.records]
    assert steps == list(range(len(steps)))
    assert all(r.recompute_matches() for r in result.records)


def test_max_turns_below_survival_threshold_is_a_legal_technical_loss() -> None:
    """Regression: a caller-supplied max_turns smaller than the configured
    survival_threshold used to raise IllegalTransitionError (WAITING ->
    BEGIN_AUDIT) instead of ending in a legal, explicit outcome."""
    assert CONFIG.movement_and_barriers.survival_threshold > 5
    deps = make_deps(CONFIG, FakeGateway(), "uid-cap", CFG_SHA, seed=3)
    runtime = SubGameRuntime(deps)
    result = _run(runtime, max_turns=5)
    assert result.result is SubGameResult.TECHNICAL_LOSS
    assert result.reason == "turn cap exhausted before a natural sub-game outcome"
    assert result.steps_taken == 5
    assert runtime.state.machine.state is PeerState.ERROR


def test_no_audit_for_a_turn_cap_aborted_game() -> None:
    """The audit must not claim a completed, verified sub-game when the
    game only ended because an artificial test/local turn cap was hit."""
    deps = make_deps(CONFIG, FakeGateway(), "uid-noaudit", CFG_SHA, seed=3)
    result = _run(SubGameRuntime(deps), max_turns=5)
    assert result.result is SubGameResult.TECHNICAL_LOSS
    assert result.audit is None


def test_exit_while_waiting_is_a_legal_technical_loss() -> None:
    deps = make_deps(CONFIG, FakeGateway(), "uid-ew", CFG_SHA, seed=1)
    runtime = SubGameRuntime(deps)
    runtime._fast_forward_to_waiting()
    assert runtime.state.machine.state is PeerState.WAITING
    result = runtime.abort("external abort while waiting")
    assert result.result is SubGameResult.TECHNICAL_LOSS
    assert result.audit is None
    assert runtime.state.machine.state is PeerState.ERROR


def test_exit_while_thinking_is_a_legal_technical_loss() -> None:
    deps = make_deps(CONFIG, FakeGateway(), "uid-et", CFG_SHA, seed=1)
    runtime = SubGameRuntime(deps)
    runtime._fast_forward_to_waiting()
    runtime.state.machine.apply(TransitionEvent(kind=EventKind.BEGIN_TURN))
    assert runtime.state.machine.state is PeerState.THINKING
    result = runtime.abort("external abort while thinking")
    assert result.result is SubGameResult.TECHNICAL_LOSS
    assert result.audit is None
    assert runtime.state.machine.state is PeerState.ERROR


def test_cancellation_mid_turn_reaches_a_legal_state_and_reraises() -> None:
    """A real asyncio cancellation delivered while genuinely suspended
    mid-turn must never hang, must re-raise (never be silently swallowed),
    and must leave the state machine in a legal (ERROR) state."""

    async def scenario() -> PeerState:
        deps = make_deps(CONFIG, BlockingGateway(), "uid-cancel", CFG_SHA, seed=1)
        runtime = SubGameRuntime(deps)
        task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return runtime.state.machine.state

    final_state = asyncio.run(scenario())
    assert final_state is PeerState.ERROR


def test_audit_begins_only_after_a_legal_terminal_state() -> None:
    deps = make_deps(CONFIG, FakeGateway(), "uid-audit", CFG_SHA, seed=7)
    result = _run(SubGameRuntime(deps))
    assert result.result is SubGameResult.SURVIVAL
    assert result.audit is not None and result.audit.verified


def test_deterministic_outcome_across_repeated_runs() -> None:
    outcomes = set()
    for _ in range(3):
        deps = make_deps(CONFIG, FakeGateway(), "uid-det", CFG_SHA, seed=7)
        result = _run(SubGameRuntime(deps))
        outcomes.add((result.result, result.steps_taken, result.thief_score))
    assert len(outcomes) == 1
