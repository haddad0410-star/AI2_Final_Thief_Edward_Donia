"""Regression: a real opponent that IS reachable but rejects a call at the
MCP protocol level (e.g. an unknown tool name) must be classified as
PeerUnavailableError, not left to crash the caller as an unhandled
fastmcp.exceptions.ToolError. Found while wiring the Thief CLI's real-HTTP
tests (session recovery step B, Task 7)."""

from __future__ import annotations

import asyncio

import pytest
from _port_utils import HOST, free_tcp_port, start_test_server, stop_test_server

from thief_peer.domain.roles import Role
from thief_peer.infrastructure.mcp_client import PeerUnavailableError, call_receive_turn
from thief_peer.infrastructure.mcp_server import build_peer_server


def test_unknown_tool_on_a_reachable_peer_is_peer_unavailable() -> None:
    async def scenario() -> None:
        port = free_tcp_port()
        # A REAL, reachable server -- but the Batch-1 negotiation-only
        # surface, with no receive_turn tool registered at all.
        mcp, _ = build_peer_server(Role.POLICE, "c" * 64)
        server = await start_test_server(mcp, port)
        try:
            with pytest.raises(PeerUnavailableError):
                await call_receive_turn(f"http://{HOST}:{port}/mcp", {"message_type": "commitment"})
        finally:
            await stop_test_server(server)

    asyncio.run(scenario())
