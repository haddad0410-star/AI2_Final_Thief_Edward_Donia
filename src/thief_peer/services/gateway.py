"""OpponentGateway: the seam between the sub-game runtime and the opponent.

Production uses :class:`HttpOpponentGateway`, which speaks REAL FastMCP HTTP via
``mcp_client``. Tests inject a fake gateway (mocks are test-only). The gateway
returns the opponent's ACK and any *public* turn info (police scent grid, hint,
capture claim) -- it can never surface the opponent's true position, which this
peer is not entitled to and never receives.

Session recovery step C, Task 5: the real opponent's public turn info is never
embedded in a message WE sent (no peer can know the other's move before it
commits its own) -- it arrives independently, asynchronously, as the
opponent's OWN outbound ``reveal`` call into OUR OWN server's inbox. So on a
real reveal delivery, :class:`HttpOpponentGateway` polls the local inbox
(bounded, never hangs) for the opponent's matching reveal and folds it into
the same ``opponent_turn`` key the runtime and every existing fake gateway
already expect -- the ``OpponentGateway`` Protocol itself is unchanged.
"""

from __future__ import annotations

import asyncio
from typing import Protocol

from thief_peer.infrastructure.inbox import BoundedInbox
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

    def __init__(
        self,
        url: str,
        local_inbox: BoundedInbox,
        timeout_seconds: float = 30.0,
        *,
        poll_interval: float = 0.1,
        max_polls: int = 300,
        opponent_token: str | None = None,
    ) -> None:
        self._url = url
        self._local_inbox = local_inbox
        self._timeout = timeout_seconds
        self._poll_interval = poll_interval
        self._max_polls = max_polls
        self._opponent_token = opponent_token

    async def deliver_turn(self, message: dict) -> dict:
        ack = await call_receive_turn(self._url, message, self._timeout, token=self._opponent_token)
        if message.get("message_type") != "reveal" or not ack.get("ok"):
            return ack
        envelope = message["envelope"]
        opponent_turn = await self._await_opponent_reveal(
            envelope["sub_game_number"], envelope["step"]
        )
        if opponent_turn is None:
            return {
                "ok": False,
                "error_code": "NO_OPPONENT_REVEAL",
                "reason": "no opponent reveal received within poll budget",
            }
        return {**ack, "opponent_turn": opponent_turn}

    async def deliver_audit(self, payload: dict) -> dict:
        return await call_submit_audit(
            self._url, payload, self._timeout, token=self._opponent_token
        )

    async def _await_opponent_reveal(self, sub_game_number: int, step: int) -> dict | None:
        def _is_matching_reveal(message: dict) -> bool:
            env = message.get("envelope", {})
            return (
                message.get("message_type") == "reveal"
                and env.get("sub_game_number") == sub_game_number
                and env.get("step") == step
            )

        for _ in range(self._max_polls):
            message = self._local_inbox.pop_matching(_is_matching_reveal)
            if message is not None:
                self._prune_consumed_commitment(message)
                return message.get("reveal", {})
            await asyncio.sleep(self._poll_interval)
        return None

    def _prune_consumed_commitment(self, reveal_message: dict) -> None:
        """A ``commitment`` is only needed until its matching ``reveal`` has
        been consumed; nothing else ever pops it, so across a multi-sub-game
        series it would otherwise accumulate without bound and eventually
        exhaust the bounded inbox's capacity (a real defect surfaced by
        session recovery step C, Task 7's real six-sub-game series -- see
        _post4b_supplementary_evidence/audit/risk_register.md)."""
        env = reveal_message.get("envelope", {})

        def _is_matching_commitment(message: dict) -> bool:
            other = message.get("envelope", {})
            return (
                message.get("message_type") == "commitment"
                and other.get("sub_game_number") == env.get("sub_game_number")
                and other.get("step") == env.get("step")
                and other.get("sender") == env.get("sender")
            )

        self._local_inbox.pop_matching(_is_matching_commitment)
