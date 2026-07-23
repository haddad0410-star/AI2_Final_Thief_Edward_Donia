"""Batch 4B: proves ``deliver_commit_and_reveal`` reports REAL per-substep
progress (commit_sent/ack_received/reveal_sent), not a hardcoded or
collapsed single pass/fail flag -- for the GUI protocol-status panel.
"""

from __future__ import annotations

import asyncio

import pytest

from thief_peer.infrastructure.mcp_client import PeerUnavailableError
from thief_peer.services.turn_exchange import ExchangeError, deliver_commit_and_reveal


class _FakeGateway:
    def __init__(self, responses) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def deliver_turn(self, message: dict) -> dict:
        self.calls += 1
        response = self._responses[self.calls - 1]
        if isinstance(response, Exception):
            raise response
        return response


def _run(gateway) -> ExchangeError:
    with pytest.raises(ExchangeError) as excinfo:
        asyncio.run(deliver_commit_and_reveal(gateway, {"c": 1}, {"r": 1}))
    return excinfo.value


def test_success_reports_all_three_true() -> None:
    gateway = _FakeGateway([{"ok": True}, {"ok": True, "opponent_turn": {}}])
    outcome = asyncio.run(deliver_commit_and_reveal(gateway, {"c": 1}, {"r": 1}))
    assert (
        outcome.progress.commit_sent,
        outcome.progress.ack_received,
        outcome.progress.reveal_sent,
    ) == (
        True,
        True,
        True,
    )
    assert gateway.calls == 2


def test_commit_rejected_reports_least_progress() -> None:
    gateway = _FakeGateway([{"ok": False}])
    error = _run(gateway)
    assert (
        error.progress.commit_sent,
        error.progress.ack_received,
        error.progress.reveal_sent,
    ) == (
        True,
        False,
        False,
    )
    assert gateway.calls == 1


def test_reveal_rejected_reports_more_progress_than_commit_rejected() -> None:
    gateway = _FakeGateway([{"ok": True}, {"ok": False}])
    error = _run(gateway)
    assert (
        error.progress.commit_sent,
        error.progress.ack_received,
        error.progress.reveal_sent,
    ) == (
        True,
        True,
        True,
    )
    assert gateway.calls == 2


def test_unreachable_on_commit_vs_unreachable_on_reveal_differ() -> None:
    """Same exception type raised at two different points must still yield
    two different real progress signatures -- proves progress is tracked
    live around each call, never guessed from the exception alone."""
    early_gateway = _FakeGateway([PeerUnavailableError("refused")])
    early = _run(early_gateway)
    assert (
        early.progress.commit_sent,
        early.progress.ack_received,
        early.progress.reveal_sent,
    ) == (
        False,
        False,
        False,
    )

    late_gateway = _FakeGateway([{"ok": True}, PeerUnavailableError("refused")])
    late = _run(late_gateway)
    assert (late.progress.commit_sent, late.progress.ack_received, late.progress.reveal_sent) == (
        True,
        True,
        False,
    )

    early_flags = (
        early.progress.commit_sent,
        early.progress.ack_received,
        early.progress.reveal_sent,
    )
    late_flags = (late.progress.commit_sent, late.progress.ack_received, late.progress.reveal_sent)
    assert early_flags != late_flags
