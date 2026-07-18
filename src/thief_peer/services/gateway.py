"""OpponentGateway: the seam between the sub-game runtime and the opponent.

Production uses :class:`HttpOpponentGateway`, which speaks REAL FastMCP HTTP via
``mcp_client``. Tests inject a fake gateway (mocks are test-only). The gateway
returns the opponent's ACK and any *public* turn info (police scent grid, hint,
capture claim) -- it can never surface the opponent's true position, which this
peer is not entitled to and never receives.
"""

from __future__ import annotations

from typing import Protocol

from thief_peer.infrastructure.mcp_client import call_receive_turn, call_submit_audit


class OpponentGateway(Protocol):
    """What the runtime needs from the opponent, transport-agnostic."""

    async def deliver_turn(self, message: dict) -> dict:
        """Deliver a turn message; return the opponent's ack (+ optional
        ``opponent_turn`` public info)."""
        ...

    async def deliver_audit(self, payload: dict) -> dict:
        """Deliver a final-audit payload; return the opponent's ack."""
        ...


class HttpOpponentGateway:
    """Real HTTP gateway to a live opponent MCP server."""

    def __init__(self, url: str, timeout_seconds: float = 30.0) -> None:
        self._url = url
        self._timeout = timeout_seconds

    async def deliver_turn(self, message: dict) -> dict:
        return await call_receive_turn(self._url, message, self._timeout)

    async def deliver_audit(self, payload: dict) -> dict:
        return await call_submit_audit(self._url, payload, self._timeout)
