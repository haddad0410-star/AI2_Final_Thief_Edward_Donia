"""FastMCP tool registration for the full turn protocol (Batch 2 Phase 6).

Registers ``receive_turn``, ``receive_move`` (a thin alias forwarding to the
exact same validation path), ``submit_audit`` and ``receive_control`` on a
FastMCP app, delegating all logic to a :class:`TurnRouter`. Handlers are
synchronous and return a quick ack; they never run strategy code or block.
"""

from __future__ import annotations

from fastmcp import FastMCP

from thief_peer.domain.roles import Role
from thief_peer.domain.state_machine import PeerStateMachine
from thief_peer.infrastructure.turn_router import TurnRouter


def register_game_tools(mcp: FastMCP, router: TurnRouter) -> None:
    """Attach the four turn-protocol tools to `mcp`, routed through `router`."""

    @mcp.tool
    def receive_turn(message: dict) -> dict:
        """Deliver one turn message (discriminated by message_type) into the inbox."""
        return router.handle_turn(message)

    @mcp.tool
    def receive_move(message: dict) -> dict:
        """Compatibility alias for receive_turn -- identical validation path."""
        return router.handle_turn(message)

    @mcp.tool
    def submit_audit(payload: dict) -> dict:
        """Deliver a final-audit / audit-ack / final-result message."""
        return router.handle_audit(payload)

    @mcp.tool
    def receive_control(message: dict) -> dict:
        """Optional out-of-band control channel; validated, enqueued, ignored."""
        return router.handle_control(message)


def build_game_server(
    role: Role,
    *,
    game_uid: str,
    config_sha256: str,
    machine: PeerStateMachine | None = None,
) -> tuple[FastMCP, TurnRouter]:
    """Build a FastMCP app plus a TurnRouter wired to expect the OPPONENT as
    sender (a thief peer validates that messages come from the police)."""
    router = TurnRouter(
        expected_game_uid=game_uid,
        expected_sender=role.opponent(),
        expected_config_sha256=config_sha256,
        machine=machine,
    )
    mcp: FastMCP = FastMCP(name=f"police-thief-{role.value}-game")

    @mcp.tool
    def health() -> dict:
        """Health/status check."""
        return {"status": "ok", "role": role.value}

    register_game_tools(mcp, router)
    return mcp, router
