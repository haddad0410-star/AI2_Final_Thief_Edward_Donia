"""SDK orchestration for the headless game CLIs (Batch 2, Phases 9-11).

Wires config loading, this peer's own FastMCP server (Phase 6's full turn
tool surface), the HTTP opponent gateway, and the sub-game/series runtimes
into two async entrypoints. Business logic lives here (not in ``__main__``)
per CLAUDE.md. Independent implementation (no import of the Police
repository).

The live cross-process path was validated for real in session recovery step C
(Task 5): two independent OS processes, real HTTP, real commit-reveal, ending
in a genuine capture/survival/technical-loss outcome -- see
integration_lab/evidence/session_recovery_step_c/one_subgame/. The runtimes
it drives are also covered by tests against in-process fakes.
"""

from __future__ import annotations

import json
from pathlib import Path

from thief_peer.domain.captures import SubGameResult
from thief_peer.domain.roles import Role
from thief_peer.domain.state_machine import PeerStateMachine
from thief_peer.infrastructure.game_tools import build_game_server
from thief_peer.infrastructure.server_lifecycle import ManagedServer
from thief_peer.services.game_ids import derive_game_id, derive_game_uid
from thief_peer.services.gateway import HttpOpponentGateway
from thief_peer.services.series_artifacts import write_series_artifacts
from thief_peer.services.series_runtime import run_series
from thief_peer.services.subgame_deps import SubGameDeps, make_deps
from thief_peer.services.subgame_runtime import SubGameRuntime
from thief_peer.shared.config_loader import load_private_config, load_shared_config, sha256_hex


def _load(config_dir: Path):
    shared = load_shared_config(config_dir / "game.json")
    private = load_private_config(config_dir / "game.toml")
    config_sha = sha256_hex(config_dir / "game.json")
    group_ids = shared.agreed_between
    game_id = derive_game_id(group_ids)
    game_uid = derive_game_uid(config_sha, group_ids)
    return shared, private, config_sha, game_id, game_uid


async def _serve(config_sha: str, game_uid: str, machine: PeerStateMachine, port: int):
    mcp, router = build_game_server(
        Role.THIEF, game_uid=game_uid, config_sha256=config_sha, machine=machine
    )
    server = ManagedServer(mcp, "127.0.0.1", port)
    await server.start()
    return server, router


async def run_subgame_headless(config_dir: Path, opponent_url: str) -> dict:
    """Run one sub-game against a live opponent server; return a JSON-safe summary."""
    shared, private, config_sha, game_id, game_uid = _load(config_dir)
    machine = PeerStateMachine()
    server, router = await _serve(config_sha, game_uid, machine, private.network.my_port)
    gateway = HttpOpponentGateway(opponent_url, router.turn_inbox)
    deps = make_deps(shared, gateway, game_uid, config_sha, seed=private.seed)
    try:
        result = await SubGameRuntime(deps, machine=machine).run()
    finally:
        await server.stop()
    return {
        "mode": "run-subgame",
        "game_id": game_id,
        "game_uid": game_uid,
        "result": result.result.value,
        "steps": result.steps_taken,
        "reason": result.reason,
        "final_state": machine.state.value,
    }


async def run_series_headless(
    config_dir: Path,
    opponent_url: str,
    smoke: bool,
    *,
    artifacts_dir: Path | None = None,
) -> dict:
    """Run a full (or --smoke single) series against a live opponent server.

    When `artifacts_dir` is given, writes the four standardized JSON
    artifacts via `series_artifacts.write_series_artifacts` -- reflecting
    exactly what happened, including a series that ended early on a
    technical loss.
    """
    shared, private, config_sha, game_id, game_uid = _load(config_dir)
    num_games = 1 if smoke else shared.network_and_league.num_games
    if smoke:
        print("SMOKE TEST ONLY: running a single sub-game, not the full 6-game series.")
    machine = PeerStateMachine()
    server, router = await _serve(config_sha, game_uid, machine, private.network.my_port)

    def deps_factory(index: int) -> SubGameDeps:
        gateway = HttpOpponentGateway(opponent_url, router.turn_inbox)
        return make_deps(shared, gateway, game_uid, config_sha, seed=private.seed + index)

    try:
        series = await run_series(deps_factory, num_games=num_games, machine=machine)
    finally:
        await server.stop()
    written_artifacts: list[str] = []
    if artifacts_dir is not None:
        paths = write_series_artifacts(
            artifacts_dir, config_dir, private, game_id, game_uid, config_sha, series
        )
        written_artifacts = [str(p) for p in paths]
    return {
        "mode": "run-series",
        "game_id": game_id,
        "game_uid": game_uid,
        "sub_games_played": len(series.sub_games),
        "police_total": series.police_total,
        "thief_total": series.thief_total,
        "terminated_reason": series.terminated_reason,
        "final_state": series.final_state.value,
        "artifacts_written": written_artifacts,
    }


def summary_exit_code(summary: dict) -> int:
    """0 for a clean finish, 1 for a technical loss / dispute."""
    if summary.get("result") == SubGameResult.TECHNICAL_LOSS.value:
        return 1
    if summary.get("terminated_reason", "completed") != "completed":
        return 1
    return 0


def print_summary(summary: dict) -> None:
    print(json.dumps(summary, indent=2))
