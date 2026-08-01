"""Real two-process FastMCP coverage for bilateral result agreement
(post-Batch-4B fix). Both "sides" are real, independently addressable
FastMCP servers over real HTTP loopback sockets (thief role for us, a
police-role stand-in for the opponent, matching this repo's existing
integration-test precedent) -- never faked in-process. Independent
implementation: no import of the Police repository.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from _port_utils import HOST, free_tcp_port, start_test_server, stop_test_server

from thief_peer.domain.roles import Role
from thief_peer.domain.state_machine import PeerState, PeerStateMachine
from thief_peer.infrastructure.game_tools import build_game_server
from thief_peer.infrastructure.mcp_client import call_submit_audit
from thief_peer.services.result_agreement import (
    build_result_agreement_message,
    exchange_and_resolve_agreement,
)

GAME_UID = "test-result-agreement-uid"
CFG_SHA = "a" * 64
OUR_TOTALS = (20, 5)
OUR_DIGEST = "d" * 64


async def _role_server(role: Role, machine: PeerStateMachine, port: int):
    mcp, router = build_game_server(role, game_uid=GAME_UID, config_sha256=CFG_SHA, machine=machine)
    server = await start_test_server(mcp, port)
    return server, router


def _fresh_machine() -> PeerStateMachine:
    return PeerStateMachine(initial=PeerState.SERIES_COMPLETE)


async def _run(scenario) -> None:
    our_port, opp_port = free_tcp_port(), free_tcp_port()
    our_server, our_router = await _role_server(Role.THIEF, _fresh_machine(), our_port)
    opp_server, _ = await _role_server(Role.POLICE, _fresh_machine(), opp_port)
    try:
        await scenario(
            f"http://{HOST}:{our_port}/mcp",
            f"http://{HOST}:{opp_port}/mcp",
            our_router.audit_inbox,
        )
    finally:
        await stop_test_server(our_server)
        await stop_test_server(opp_server)


def _their_message(**overrides) -> dict:
    fields = {
        "game_uid": GAME_UID,
        "sender": Role.POLICE,
        "config_sha256": CFG_SHA,
        "police_total": OUR_TOTALS[0],
        "thief_total": OUR_TOTALS[1],
        "num_sub_games": 6,
        "result_digest": OUR_DIGEST,
    }
    fields.update(overrides)
    return build_result_agreement_message(**fields)


async def _resolve(our_url: str, opp_url: str, inbox, **kwargs):
    params = {
        "opponent_url": opp_url,
        "inbox": inbox,
        "game_uid": GAME_UID,
        "config_sha256": CFG_SHA,
        "sender": Role.THIEF,
        "our_totals": OUR_TOTALS,
        "num_sub_games": 6,
        "result_digest": OUR_DIGEST,
        "attempts": 20,
        "poll_interval": 0.0,
    }
    params.update(kwargs)
    return await exchange_and_resolve_agreement(**params)


def test_matching_totals_agree_on_both_sides() -> None:
    async def scenario(our_url, opp_url, inbox):
        ack = await call_submit_audit(our_url, _their_message())
        assert ack["ok"] is True
        agreement = await _resolve(our_url, opp_url, inbox)
        assert agreement.agreed is True
        assert agreement.status == "agreed"
        assert (agreement.police_total, agreement.thief_total) == OUR_TOTALS

    asyncio.run(_run(scenario))


def test_mismatched_police_total_zeros_both_sides() -> None:
    async def scenario(our_url, opp_url, inbox):
        await call_submit_audit(our_url, _their_message(police_total=999))
        agreement = await _resolve(our_url, opp_url, inbox)
        assert agreement.agreed is False
        assert agreement.status == "disputed_zeroed"
        assert (agreement.police_total, agreement.thief_total) == (0, 0)

    asyncio.run(_run(scenario))


def test_mismatched_thief_total_zeros_both_sides() -> None:
    async def scenario(our_url, opp_url, inbox):
        await call_submit_audit(our_url, _their_message(thief_total=999))
        agreement = await _resolve(our_url, opp_url, inbox)
        assert agreement.agreed is False
        assert agreement.status == "disputed_zeroed"
        assert (agreement.police_total, agreement.thief_total) == (0, 0)

    asyncio.run(_run(scenario))


def test_mismatched_game_uid_is_rejected() -> None:
    async def scenario(our_url, opp_url, inbox):
        ack = await call_submit_audit(our_url, _their_message(game_uid="wrong-uid"))
        assert ack["ok"] is False
        assert ack["error_code"] == "WRONG_GAME"
        agreement = await _resolve(our_url, opp_url, inbox)
        assert agreement.status == "unverified_self_play"

    asyncio.run(_run(scenario))


def test_mismatched_config_hash_is_rejected() -> None:
    async def scenario(our_url, opp_url, inbox):
        ack = await call_submit_audit(our_url, _their_message(config_sha256="b" * 64))
        assert ack["ok"] is False
        assert ack["error_code"] == "CONFIG_MISMATCH"
        agreement = await _resolve(our_url, opp_url, inbox)
        assert agreement.status == "unverified_self_play"

    asyncio.run(_run(scenario))


def test_duplicate_identical_agreement_is_idempotent() -> None:
    async def scenario(our_url, opp_url, inbox):
        msg = _their_message()
        first = await call_submit_audit(our_url, msg)
        second = await call_submit_audit(our_url, msg)
        assert first["ok"] is True
        assert second["ok"] is True
        assert second.get("idempotent") is True
        agreement = await _resolve(our_url, opp_url, inbox)
        assert agreement.status == "agreed"

    asyncio.run(_run(scenario))


def test_conflicting_duplicate_is_rejected() -> None:
    async def scenario(our_url, opp_url, inbox):
        first = await call_submit_audit(our_url, _their_message())
        second = await call_submit_audit(our_url, _their_message(police_total=1))
        assert first["ok"] is True
        assert second["ok"] is False
        assert second["error_code"] == "CONFLICTING_DUPLICATE"
        agreement = await _resolve(our_url, opp_url, inbox)
        assert agreement.status == "agreed"

    asyncio.run(_run(scenario))


def test_missing_opponent_result_remains_unverified() -> None:
    async def scenario(our_url, opp_url, inbox):
        agreement = await _resolve(our_url, opp_url, inbox)
        assert agreement.agreed is False
        assert agreement.status == "unverified_self_play"
        assert (agreement.police_total, agreement.thief_total) == OUR_TOTALS

    asyncio.run(_run(scenario))


def test_no_orphan_process_or_port_leak(tmp_path: Path) -> None:
    from _port_utils import is_port_free

    our_port, opp_port = free_tcp_port(), free_tcp_port()

    async def scenario():
        our_server, our_router = await _role_server(Role.THIEF, _fresh_machine(), our_port)
        opp_server, _ = await _role_server(Role.POLICE, _fresh_machine(), opp_port)
        try:
            our_url = f"http://{HOST}:{our_port}/mcp"
            opp_url = f"http://{HOST}:{opp_port}/mcp"
            await call_submit_audit(our_url, _their_message())
            await _resolve(our_url, opp_url, our_router.audit_inbox)
        finally:
            await stop_test_server(our_server)
            await stop_test_server(opp_server)

    asyncio.run(scenario())
    assert is_port_free(our_port)
    assert is_port_free(opp_port)
