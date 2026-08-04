"""Batch 3.6 Task 6: capture-correctness boundary audit.

Most edge cases (conflicting/duplicate/stale claims, false capture claim,
deadline exceeded, no response) are already covered by
failure_drills.py (18/18 passing, rerun this batch; a development-workspace
script under the full project workspace's integration_lab/scripts/, not
included in this standalone package) and
tests/unit/test_capture_response_delay.py (true/false/barrier
claims, one-turn-delayed confirmation). This file adds the one boundary
case not yet explicitly tested: capture and the survival threshold being
reachable on the SAME final turn.
"""

from __future__ import annotations

import asyncio

from _thief_series_fixtures import CFG_SHA, CONFIG, THIEF_START

from thief_peer.domain.captures import SubGameResult
from thief_peer.domain.hints import HintIntent
from thief_peer.services.subgame_runtime import SubGameRuntime, make_deps
from thief_peer.strategy.decision import Decision


class _StationaryBrain:
    """Never moves -- isolates the claim-timing boundary condition."""

    def decide(self, ctx):
        from thief_peer.domain.positions import Direction

        return Decision(direction=Direction.STAY, intent=HintIntent.TRUTH)


class _LastTurnClaimGateway:
    """Acks everything; returns a WRONG capture_claim on every turn except
    the very last legal turn (survival_threshold - 1), where it returns
    the thief's real (stationary) start cell."""

    def __init__(self, correct_cell, wrong_cell, last_turn_step: int) -> None:
        self._correct = correct_cell
        self._wrong = wrong_cell
        self._last_turn_step = last_turn_step
        self._step = 0
        self.turns_seen: list[str] = []

    async def deliver_turn(self, message: dict) -> dict:
        self.turns_seen.append(message["message_type"])
        ack: dict = {"ok": True}
        if message["message_type"] == "reveal":
            claim = self._correct if self._step == self._last_turn_step else self._wrong
            ack["opponent_turn"] = {"capture_claim": claim}
            self._step += 1
        return ack

    async def deliver_audit(self, payload: dict) -> dict:
        return {"ok": True}


def _run(runtime: SubGameRuntime, **kw):
    return asyncio.run(runtime.run(**kw))


def test_capture_takes_priority_over_survival_on_the_same_boundary_turn() -> None:
    """A truthful capture claim delivered on the LAST legal turn (the same
    turn survival would otherwise be declared) must still resolve as
    CAPTURE, not SURVIVAL -- resolve_capture is checked before the
    survival-threshold check in _resolve_and_advance."""
    threshold = CONFIG.movement_and_barriers.survival_threshold
    gw = _LastTurnClaimGateway(
        correct_cell=THIEF_START, wrong_cell=[6, 6], last_turn_step=threshold - 1
    )
    deps = make_deps(CONFIG, gw, "uid-boundary", CFG_SHA, seed=9, brain=_StationaryBrain())
    result = _run(SubGameRuntime(deps))
    assert result.result is SubGameResult.CAPTURE
    assert result.thief_score == CONFIG.scoring.capture_thief
