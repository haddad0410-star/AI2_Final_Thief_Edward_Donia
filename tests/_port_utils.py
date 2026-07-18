"""Shared test-only helpers for real, isolated FastMCP HTTP servers over
loopback.

Every integration test that spins up a live server should get its own
dynamically allocated free port -- never a hardcoded one -- so tests never
collide with each other, a leftover server from a previous run, or an
unrelated process on the machine (see the sibling Police repo's Batch-2
port-collision recovery for the concrete failure this avoids).
"""

from __future__ import annotations

import socket

from fastmcp import FastMCP

from thief_peer.infrastructure.server_lifecycle import ManagedServer

HOST = "127.0.0.1"


def free_tcp_port(host: str = HOST) -> int:
    """Return a currently-unused local TCP port, assigned by the OS.

    Binds a throwaway socket to port 0 so the kernel picks a free ephemeral
    port, reads it back, then releases the socket immediately so the real
    server can bind it a moment later.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind((host, 0))
        return probe.getsockname()[1]


def is_port_free(port: int, host: str = HOST) -> bool:
    """True if ``port`` can be bound right now the same way a real server
    would bind it (i.e. with ``SO_REUSEADDR``, matching asyncio/uvicorn's own
    default on POSIX).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


async def start_test_server(mcp: FastMCP, port: int, host: str = HOST) -> ManagedServer:
    """Start ``mcp``'s real HTTP ASGI app via the production-grade
    :class:`~thief_peer.infrastructure.server_lifecycle.ManagedServer`."""
    server = ManagedServer(mcp, host, port)
    await server.start()
    return server


async def stop_test_server(server: ManagedServer) -> None:
    """Stop a server started with :func:`start_test_server`, waiting for a
    genuinely graceful shutdown before returning."""
    await server.stop()
