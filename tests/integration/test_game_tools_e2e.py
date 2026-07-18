"""Phase 6: end-to-end over REAL FastMCP HTTP -- a game server exposes the turn
tools and an in-process client drives one lifecycle, an audit, and a control
message. Also checks the unavailable-opponent path."""

from __future__ import annotations

import asyncio

from thief_peer.domain.roles import Role
from thief_peer.infrastructure.game_tools import build_game_server
from thief_peer.infrastructure.mcp_client import (
    PeerUnavailableError,
    call_receive_control,
    call_receive_turn,
    call_submit_audit,
    wait_for_health,
)
from thief_peer.infrastructure.server_lifecycle import (
    IntentionalShutdown,
    run_server_managed,
    stop_server,
)

UID = "uid-e2e"
CFG = "e" * 64
PORT = 18991
URL = f"http://127.0.0.1:{PORT}/mcp"


def _env(step: int, cid: str) -> dict:
    return {
        "schema_version": "1.0",
        "correlation_id": cid,
        "game_id": "g",
        "game_uid": UID,
        "sub_game_number": 1,
        "step": step,
        "sender": "police",
        "timestamp": "2026-07-18T00:00:00+00:00",
        "sequence_id": step,
    }


def test_full_turn_lifecycle_over_http() -> None:
    async def scenario() -> None:
        mcp, router = build_game_server(Role.THIEF, game_uid=UID, config_sha256=CFG)
        shutdown = IntentionalShutdown()
        task = asyncio.create_task(run_server_managed(mcp, "127.0.0.1", PORT, shutdown))
        try:
            await wait_for_health(URL, attempts=15, delay_seconds=0.3)
            commit = {
                "envelope": _env(0, "c0"),
                "message_type": "commitment",
                "commit_hash": "a" * 64,
            }
            ack = {"envelope": _env(0, "a0"), "message_type": "commit_ack", "commit_hash": "a" * 64}
            reveal = {
                "envelope": _env(0, "r0"),
                "message_type": "reveal",
                "hint_text": "the eastern district feels wrong",
                "hint_intent": "lie",
            }
            assert (await call_receive_turn(URL, commit))["ok"] is True
            assert (await call_receive_turn(URL, ack))["ok"] is True
            assert (await call_receive_turn(URL, reveal))["ok"] is True
            # receive_move alias hits the same path (next step's commitment).
            move_msg = {
                "envelope": _env(1, "c1"),
                "message_type": "commitment",
                "commit_hash": "b" * 64,
            }
            assert (await call_receive_turn(URL, move_msg))["ok"] is True

            audit = {
                "envelope": _env(0, "au"),
                "message_type": "audit",
                "records": [],
                "result_claim": "survival",
            }
            assert (await call_submit_audit(URL, audit))["ok"] is True
            ctrl = {"envelope": _env(0, "ct"), "kind": "status", "status_text": "ready"}
            assert (await call_receive_control(URL, ctrl))["ok"] is True
            assert router.turn_inbox.size() == 4
        finally:
            await stop_server(task, shutdown)

    asyncio.run(scenario())


def test_unavailable_opponent_raises() -> None:
    async def scenario() -> None:
        bad_url = "http://127.0.0.1:18999/mcp"
        raised = False
        try:
            await wait_for_health(bad_url, attempts=2, delay_seconds=0.1)
        except PeerUnavailableError:
            raised = True
        assert raised

    asyncio.run(scenario())
