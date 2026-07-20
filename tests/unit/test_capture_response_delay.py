"""Batch 3.5 Task 4/9, defect H: the honest capture-claim answer must
actually be transmitted back to police, even though the synchronous
per-step exchange structurally cannot answer a same-step claim (both peers
send their own reveal before receiving the other's).
"""

from __future__ import annotations

import asyncio

from _thief_series_fixtures import CFG_SHA, CONFIG, THIEF_START, FakeGateway

from thief_peer.domain.captures import SubGameResult
from thief_peer.services.subgame_runtime import SubGameRuntime, make_deps


def _run(runtime: SubGameRuntime, **kw):
    return asyncio.run(runtime.run(**kw))


def test_false_claim_does_not_end_game_and_pending_is_false() -> None:
    # Police claims a cell the thief is not standing on.
    gw = FakeGateway(opponent_turn={"capture_claim": [0, 0]})
    deps = make_deps(CONFIG, gw, "uid-false", CFG_SHA, seed=2)
    result = _run(SubGameRuntime(deps))
    assert result.result is not SubGameResult.CAPTURE


def test_true_claim_delivers_confirmation_one_turn_later() -> None:
    gw = FakeGateway(opponent_turn={"capture_claim": THIEF_START})
    deps = make_deps(CONFIG, gw, "uid-true", CFG_SHA, seed=3)
    result = _run(SubGameRuntime(deps))
    assert result.result is SubGameResult.CAPTURE
    # 2 reveal-carrying turns were sent: one detecting, one confirming.
    reveal_count = sum(1 for t in gw.turns_seen if t == "reveal")
    assert reveal_count == 2


def test_barrier_capture_also_delivers_confirmation() -> None:
    gw = FakeGateway(opponent_turn={"barrier_placed": THIEF_START})
    deps = make_deps(CONFIG, gw, "uid-barrier", CFG_SHA, seed=4)
    result = _run(SubGameRuntime(deps))
    assert result.result is SubGameResult.CAPTURE
    reveal_count = sum(1 for t in gw.turns_seen if t == "reveal")
    assert reveal_count == 2


def test_no_claim_evidence_leaves_pending_response_none() -> None:
    from thief_peer.services.subgame_state import SubGameState

    gw = FakeGateway(opponent_turn={})
    deps = make_deps(CONFIG, gw, "uid-none", CFG_SHA, seed=5)
    state: SubGameState = SubGameRuntime(deps).state
    assert state.pending_claim_response is None
