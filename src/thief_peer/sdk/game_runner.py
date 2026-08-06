"""SDK orchestration for the headless game CLIs: config loading, this peer's
own FastMCP server, the HTTP opponent gateway, sub-game/series runtimes, and
end-of-series bilateral result agreement. Independent implementation (no
import of the Police repository); business logic lives here, not `__main__`.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

from thief_peer.domain.captures import SubGameResult
from thief_peer.domain.roles import Role
from thief_peer.domain.state_machine import PeerStateMachine
from thief_peer.infrastructure.game_tools import build_game_server
from thief_peer.infrastructure.mcp_client import PeerUnavailableError, wait_for_health
from thief_peer.infrastructure.outbound_pacer import OutboundPacer
from thief_peer.infrastructure.server_lifecycle import ManagedServer
from thief_peer.sdk.public_mode import build_public_middleware
from thief_peer.services.game_ids import derive_game_id, derive_game_uid
from thief_peer.services.gateway import HttpOpponentGateway
from thief_peer.services.result_agreement import finalize_series_agreement
from thief_peer.services.series_artifacts import write_series_artifacts
from thief_peer.services.series_runtime import run_series
from thief_peer.services.subgame_deps import SubGameDeps, make_deps
from thief_peer.shared.config_loader import (
    load_private_config,
    load_rate_limits,
    load_shared_config,
    sha256_hex,
)


async def _await_opponent_ready(opponent_url: str, opponent_token: str | None = None) -> None:
    # Covers ordinary two-terminal startup skew; a genuine no-show still
    # fails honestly at the first real gameplay call below, unchanged.
    # `opponent_token` (Gate A1) is required when the opponent runs
    # `--public` -- without it this poll is rejected with a real 401, not a
    # transient connectivity failure.
    with contextlib.suppress(PeerUnavailableError):
        await wait_for_health(opponent_url, attempts=100, delay_seconds=0.3, token=opponent_token)


def _load(config_dir: Path):
    shared = load_shared_config(config_dir / "game.json")
    private = load_private_config(config_dir / "game.toml")
    config_sha = sha256_hex(config_dir / "game.json")
    group_ids = shared.agreed_between
    game_id = derive_game_id(group_ids)
    game_uid = derive_game_uid(config_sha, group_ids)
    return shared, private, config_sha, game_id, game_uid


async def _serve(
    config_sha: str,
    game_uid: str,
    machine: PeerStateMachine,
    port: int,
    *,
    public_token: str | None = None,
    config_dir: Path | None = None,
):
    mcp, router = build_game_server(
        Role.THIEF, game_uid=game_uid, config_sha256=config_sha, machine=machine
    )
    middleware = build_public_middleware(mcp, public_token, config_dir) if public_token else None
    server = ManagedServer(mcp, "127.0.0.1", port, middleware=middleware)
    await server.start()
    return server, router


def _build_pacer(opponent_token: str | None, config_dir: Path) -> OutboundPacer | None:
    """A pacer is only needed when calling a ``--public`` opponent (signaled
    by possessing their token) -- ordinary local self-play never constructs
    one, so its behavior is provably unaffected."""
    if opponent_token is None:
        return None
    return OutboundPacer(load_rate_limits(config_dir / "rate_limits.json"))


async def run_series_headless(
    config_dir: Path,
    opponent_url: str,
    smoke: bool,
    *,
    artifacts_dir: Path | None = None,
    public_token: str | None = None,
    opponent_token: str | None = None,
) -> dict:
    # `artifacts_dir`, if given, gets the four standardized JSON artifacts
    # reflecting exactly what happened, including an early technical-loss end.
    shared, private, config_sha, game_id, game_uid = _load(config_dir)
    num_games = 1 if smoke else shared.network_and_league.num_games
    if smoke:
        print("SMOKE TEST ONLY: running a single sub-game, not the full 6-game series.")
    machine = PeerStateMachine()
    server, router = await _serve(
        config_sha,
        game_uid,
        machine,
        private.network.my_port,
        public_token=public_token,
        config_dir=config_dir,
    )
    await _await_opponent_ready(opponent_url, opponent_token)
    # One pacer for the WHOLE series, not per sub-game -- its window must
    # track cumulative volume across all 6 games, like the opponent's own.
    pacer = _build_pacer(opponent_token, config_dir)

    def deps_factory(index: int) -> SubGameDeps:
        gateway = HttpOpponentGateway(
            opponent_url, router.turn_inbox, opponent_token=opponent_token, pacer=pacer
        )
        return make_deps(
            shared,
            gateway,
            game_uid,
            config_sha,
            seed=private.seed + index,
            strategy_class=private.strategy.thief_class,
            strategy_weights=private.strategy.weights,
        )

    try:
        series = await run_series(
            deps_factory,
            num_games=num_games,
            machine=machine,
            opponent_url=opponent_url,
            opponent_token=opponent_token,
        )
        series = await finalize_series_agreement(
            series,
            opponent_url=opponent_url,
            inbox=router.audit_inbox,
            game_uid=game_uid,
            config_sha256=config_sha,
            role=Role.THIEF,
            opponent_token=opponent_token,
            pacer=pacer,
        )
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
        "agreed": series.agreed,
        "police_total": series.police_total,
        "thief_total": series.thief_total,
        "agreement_status": series.agreement_status,
        "terminated_reason": series.terminated_reason,
        "final_state": series.final_state.value,
        "artifacts_written": written_artifacts,
    }


def summary_exit_code(summary: dict) -> int:
    """0 = clean, agreed finish; 1 = technical loss / incomplete / disputed."""
    if summary.get("result") == SubGameResult.TECHNICAL_LOSS.value:
        return 1
    if summary.get("terminated_reason", "completed") != "completed":
        return 1
    disputed = summary.get("agreement_status") in ("disputed_zeroed", "unverified_self_play")
    return 1 if disputed or summary.get("agreed") is False else 0


def print_summary(summary: dict) -> None:
    print(json.dumps(summary, indent=2))
