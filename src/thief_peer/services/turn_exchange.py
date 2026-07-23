"""Real per-substep commit/reveal progress tracking for the GUI protocol-status
panel, extracted from ``turn_loop.py`` to stay under the 150-line cap. Wraps
the exact same two ``gateway.deliver_turn`` calls in the exact same order,
with no added delay -- purely additive observability, never a guess from
``machine.state`` or a hardcoded value.
"""

from __future__ import annotations

from dataclasses import dataclass

from thief_peer.infrastructure.mcp_client import PeerUnavailableError


@dataclass(frozen=True, slots=True)
class ExchangeProgress:
    commit_sent: bool = False
    ack_received: bool = False
    reveal_sent: bool = False


class ExchangeError(Exception):
    """Raised when either half of the exchange is rejected or unreachable;
    carries the real progress made before the failure."""

    def __init__(self, reason: str, progress: ExchangeProgress) -> None:
        super().__init__(reason)
        self.progress = progress


@dataclass(frozen=True, slots=True)
class ExchangeOutcome:
    progress: ExchangeProgress
    reveal_ack: dict


async def deliver_commit_and_reveal(
    gateway, commitment_msg: dict, reveal_msg: dict
) -> ExchangeOutcome:
    """Send commitment then reveal; real progress on success, raises
    :class:`ExchangeError` (with the real partial progress) otherwise."""
    try:
        ack = await gateway.deliver_turn(commitment_msg)
    except PeerUnavailableError as exc:
        raise ExchangeError(str(exc), ExchangeProgress()) from exc
    if not ack.get("ok"):
        raise ExchangeError(f"commitment rejected: {ack}", ExchangeProgress(commit_sent=True))
    try:
        reveal_ack = await gateway.deliver_turn(reveal_msg)
    except PeerUnavailableError as exc:
        progress = ExchangeProgress(commit_sent=True, ack_received=True)
        raise ExchangeError(str(exc), progress) from exc
    if not reveal_ack.get("ok"):
        progress = ExchangeProgress(commit_sent=True, ack_received=True, reveal_sent=True)
        raise ExchangeError(f"reveal rejected: {reveal_ack}", progress)
    progress = ExchangeProgress(commit_sent=True, ack_received=True, reveal_sent=True)
    return ExchangeOutcome(progress, reveal_ack)
