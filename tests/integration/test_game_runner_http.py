"""Real-HTTP coverage for the headless runner: runs run_subgame_headless /
run_series_headless against a bare local opponent stand-in that has no
receive_turn tool at all (the Batch-1 negotiation-only server), so the very
first turn call fails with a real, immediate ClientError -> PeerUnavailableError
-> a clean, explicit TECHNICAL_LOSS (never a hang). This exercises the real
client->server round-trip without needing a full second peer implementation.

Both this peer's own server and the opponent stand-in bind a dynamically
allocated free localhost port per test run (see ``_port_utils``).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from _port_utils import HOST, free_tcp_port, start_test_server, stop_test_server

from thief_peer.domain.roles import Role
from thief_peer.infrastructure.mcp_server import build_peer_server
from thief_peer.sdk.game_runner import (
    run_series_headless,
    run_subgame_headless,
    summary_exit_code,
)

REAL_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "thief"


def test_run_subgame_headless_against_silent_opponent(tmp_path: Path) -> None:
    async def scenario() -> None:
        opponent_port = free_tcp_port()
        mcp, _ = build_peer_server(Role.POLICE, "b" * 64)
        opp_server = await start_test_server(mcp, opponent_port)
        try:
            summary = await run_subgame_headless(
                REAL_CONFIG_DIR, f"http://{HOST}:{opponent_port}/mcp"
            )
        finally:
            await stop_test_server(opp_server)
        assert summary["mode"] == "run-subgame"
        assert summary["result"] == "technical_loss"
        assert summary["final_state"] == "error"
        assert summary_exit_code(summary) == 1

    asyncio.run(scenario())


def test_run_series_headless_smoke_against_silent_opponent(tmp_path: Path) -> None:
    async def scenario() -> None:
        opponent_port = free_tcp_port()
        mcp, _ = build_peer_server(Role.POLICE, "b" * 64)
        opp_server = await start_test_server(mcp, opponent_port)
        try:
            summary = await run_series_headless(
                REAL_CONFIG_DIR, f"http://{HOST}:{opponent_port}/mcp", smoke=True
            )
        finally:
            await stop_test_server(opp_server)
        assert summary["mode"] == "run-series"
        assert summary["terminated_reason"] == "technical_loss_ended_series"
        assert summary_exit_code(summary) == 1

    asyncio.run(scenario())


def test_run_series_headless_writes_artifacts_when_requested(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"

    async def scenario() -> dict:
        opponent_port = free_tcp_port()
        mcp, _ = build_peer_server(Role.POLICE, "b" * 64)
        opp_server = await start_test_server(mcp, opponent_port)
        try:
            return await run_series_headless(
                REAL_CONFIG_DIR,
                f"http://{HOST}:{opponent_port}/mcp",
                smoke=True,
                artifacts_dir=artifacts_dir,
            )
        finally:
            await stop_test_server(opp_server)

    summary = asyncio.run(scenario())
    written = summary["artifacts_written"]
    assert len(written) == 4  # declaration + (config, log) x1 smoke game + result
    game_id = summary["game_id"]
    paths = [
        artifacts_dir / f"declaration_{game_id}.json",
        artifacts_dir / f"config_{game_id}_g01.json",
        artifacts_dir / f"log_{game_id}_g01.json",
        artifacts_dir / f"result_{game_id}.json",
    ]
    for path in paths:
        assert path.exists(), path
    uids = {json.loads(p.read_text())["game_uid"] for p in paths}
    assert uids == {summary["game_uid"]}
