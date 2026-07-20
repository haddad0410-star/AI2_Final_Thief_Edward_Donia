"""Phase 10: six-sub-game series runtime against an in-process FAKE opponent
gateway (mocks are test-only, matching test_subgame_runtime.py's pattern).
"""

from __future__ import annotations

import asyncio

import pytest
from _thief_series_fixtures import (
    CFG_SHA,
    CONFIG,
    CONFIG_PATH,
    THIEF_START,
    BlockingGateway,
    FakeGateway,
)

from thief_peer.domain.captures import SubGameResult
from thief_peer.domain.state_machine import PeerState, PeerStateMachine
from thief_peer.services.series_runtime import run_series
from thief_peer.services.subgame_deps import make_deps
from thief_peer.shared.config_loader import load_shared_config, sha256_hex

UID = "uid-series"


def _capture_factory(*, reject_at: int | None = None):
    """A deps_factory that captures the thief on its first move every
    sub-game, except sub-game index `reject_at` (0-based), which rejects
    outright (a protocol-error technical loss)."""

    def factory(index: int):
        gw = FakeGateway(reject=(index == reject_at), opponent_turn={"capture_claim": THIEF_START})
        return make_deps(CONFIG, gw, UID, CFG_SHA, seed=index)

    return factory


def _run(factory, num_games: int, max_turns: int | None = None):
    return asyncio.run(run_series(factory, num_games=num_games, max_turns=max_turns))


def test_series_runs_exactly_num_games_sub_games() -> None:
    series = _run(_capture_factory(), num_games=6)
    assert len(series.sub_games) == 6
    assert len(series.run_results) == 6
    assert series.terminated_reason == "completed"
    assert series.final_state is PeerState.SERIES_COMPLETE


def test_unique_and_sequential_sub_game_numbers() -> None:
    series = _run(_capture_factory(), num_games=6)
    assert [r.sub_game_number for r in series.sub_games] == [1, 2, 3, 4, 5, 6]


def test_correct_reset_between_games() -> None:
    """Every sub-game starts the thief back at the SAME configured start
    cell and is captured in exactly 2 steps (one to detect the claim, one
    to deliver the honest confirmation -- Batch 3.5 Task 4/9 defect H fix)
    -- proves position/step/records are freshly reset each sub-game, not
    carried over from the last one."""
    series = _run(_capture_factory(), num_games=6)
    assert all(r.result is SubGameResult.CAPTURE for r in series.sub_games)
    assert all(r.steps_taken == 2 for r in series.sub_games)


def test_stable_game_uid_across_series() -> None:
    seen_uids: list[str] = []

    def factory(index: int):
        deps = _capture_factory()(index)
        seen_uids.append(deps.game_uid)
        return deps

    _run(factory, num_games=6)
    assert seen_uids == [UID] * 6


def test_score_aggregation() -> None:
    series = _run(_capture_factory(), num_games=6)
    per_game_thief = series.sub_games[0].thief_score
    per_game_police = series.sub_games[0].police_score
    assert series.thief_total == per_game_thief * 6
    assert series.police_total == per_game_police * 6


def test_one_technical_loss_among_otherwise_valid_games() -> None:
    """Sub-game 3 (index 2) fails technically; the series must stop there --
    never silently continue to games 4-6, and never report the aborted game
    as a valid capture/survival."""
    series = _run(_capture_factory(reject_at=2), num_games=6)
    assert len(series.sub_games) == 3
    assert len(series.run_results) == 3
    assert [r.sub_game_number for r in series.sub_games] == [1, 2, 3]
    assert series.sub_games[0].result is SubGameResult.CAPTURE
    assert series.sub_games[1].result is SubGameResult.CAPTURE
    assert series.sub_games[2].result is SubGameResult.TECHNICAL_LOSS
    assert series.sub_games[2].audit_verified is False
    assert series.terminated_reason == "technical_loss_ended_series"
    assert series.final_state is PeerState.ERROR


def test_interrupted_series_reports_only_games_actually_played() -> None:
    series = _run(_capture_factory(reject_at=0), num_games=6)
    assert len(series.sub_games) == 1
    assert len(series.run_results) == 1
    assert series.terminated_reason == "technical_loss_ended_series"


def test_cancellation_mid_series_reraises() -> None:
    async def scenario() -> None:
        def factory(index: int):
            return make_deps(CONFIG, BlockingGateway(), UID, CFG_SHA, seed=index)

        task = asyncio.create_task(run_series(factory, num_games=6))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())


def test_no_accidental_use_of_smoke_fixture() -> None:
    """`num_games` has no default -- a caller MUST explicitly choose 6
    (league) or 1 (smoke); it can never silently fall back to either."""
    with pytest.raises(TypeError):
        asyncio.run(run_series(_capture_factory()))  # type: ignore[call-arg]


def test_smoke_mode_plays_exactly_one_game() -> None:
    series = _run(_capture_factory(), num_games=1)
    assert len(series.sub_games) == 1
    assert series.final_state is PeerState.SERIES_COMPLETE


def test_binding_config_is_the_real_league_config_not_smoke() -> None:
    real = load_shared_config(CONFIG_PATH)
    assert real.network_and_league.num_games == 6
    assert sha256_hex(CONFIG_PATH) == CFG_SHA


def test_injected_machine_is_shared_and_advances() -> None:
    """A caller running its own incoming-message server (Phase 6) must be
    able to share ITS machine with the series -- e.g. TurnRouter validates
    incoming messages against the exact same lifecycle state this runtime
    advances. Regression: run_series used to always build its own private
    machine, making that sharing impossible."""
    machine = PeerStateMachine()
    series = _run_with_machine(_capture_factory(), num_games=6, machine=machine)
    assert machine.state is series.final_state
    assert machine.state is PeerState.SERIES_COMPLETE


def _run_with_machine(factory, num_games: int, machine: PeerStateMachine):
    return asyncio.run(run_series(factory, num_games=num_games, machine=machine))


def test_deterministic_outcome_across_repeated_runs() -> None:
    outcomes = set()
    for _ in range(3):
        series = _run(_capture_factory(), num_games=6)
        outcomes.add(
            (
                tuple((r.sub_game_number, r.result, r.thief_score) for r in series.sub_games),
                series.police_total,
                series.thief_total,
                series.terminated_reason,
            )
        )
    assert len(outcomes) == 1
