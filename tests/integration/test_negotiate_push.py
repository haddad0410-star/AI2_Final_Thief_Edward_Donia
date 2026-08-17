"""Real HTTP test for push_negotiate -- server run in-process, client calls
made over actual HTTP to 127.0.0.1. No mocks. Regression coverage for the
2026-08-17 finding: run_series_headless never called negotiate at all, so a
compliant opponent that requires a signed agreement before accepting real
turns would never receive one. Mirrors police_peer's identical fix -- both
peers must agree on this construction since they negotiate as one pairing."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
from pathlib import Path

from thief_peer.domain.roles import Role
from thief_peer.infrastructure.mcp_server import build_peer_server, run_server_until_cancelled
from thief_peer.sdk.negotiate_push import push_negotiate
from thief_peer.services.game_ids import build_signed_negotiate_message, canonical_terms_json
from thief_peer.shared.config_loader import load_private_config, load_shared_config

HOST = "127.0.0.1"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


async def _start(port: int):
    mcp, inbox = build_peer_server(Role.THIEF, "a" * 64)
    task = asyncio.create_task(run_server_until_cancelled(mcp, HOST, port))
    await asyncio.sleep(0.3)
    return task, inbox


async def _stop(task: asyncio.Task) -> None:
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


def test_push_negotiate_lands_a_real_signed_agreement() -> None:
    async def scenario():
        task, inbox = await _start(8961)
        try:
            shared = load_shared_config(FIXTURES / "valid_shared_game.json")
            private = load_private_config(FIXTURES / "valid_private_game.toml")
            await push_negotiate(shared, private, f"http://{HOST}:8961/mcp", "thief", None)
            assert inbox.declarations.qsize() == 1
            declared = inbox.declarations.get_nowait()
            assert declared["group_id"] == private.game.group_id
            assert declared["role"] == "thief"
            assert "signature" in declared and "terms" in declared and "nonce" in declared
        finally:
            await _stop(task)

    asyncio.run(scenario())


def test_push_negotiate_never_raises_on_unreachable_opponent() -> None:
    async def scenario():
        shared = load_shared_config(FIXTURES / "valid_shared_game.json")
        private = load_private_config(FIXTURES / "valid_private_game.toml")
        # Nothing listens on this port -- must not raise (best-effort only).
        await push_negotiate(shared, private, f"http://{HOST}:8962/mcp", "thief", None)

    asyncio.run(scenario())


def test_build_signed_negotiate_message_signature_self_verifies() -> None:
    """A receiver re-verifies SHA256(canonical_json(terms)|nonce) over the
    terms it received using the sender's nonce -- this must round-trip."""
    terms = {"board_size": 7, "num_games": 6}
    message = build_signed_negotiate_message(
        terms, group_id="ed%do111", role="thief", sub_game_number=1, correlation_id="cid"
    )
    expected = hashlib.sha256(
        (canonical_terms_json(terms) + "|" + message["nonce"]).encode("utf-8")
    ).hexdigest()
    assert message["signature"] == expected
    assert message["envelope"] == {"correlation_id": "cid", "group_id": "ed%do111"}
