"""``run-subgame`` (single sub-game) entrypoint. Split out of
``game_runner.py`` (Gate A1: `public_token`/`opponent_token` plumbing pushed
that file over the 150-line cap) -- shares `_load`/`_serve` from there
rather than duplicating them.
"""

from __future__ import annotations

from pathlib import Path

from thief_peer.domain.state_machine import PeerStateMachine
from thief_peer.sdk.game_runner import _await_opponent_ready, _build_pacer, _load, _serve
from thief_peer.services.gateway import HttpOpponentGateway
from thief_peer.services.subgame_deps import make_deps
from thief_peer.services.subgame_runtime import SubGameRuntime


async def run_subgame_headless(
    config_dir: Path,
    opponent_url: str,
    *,
    public_token: str | None = None,
    opponent_token: str | None = None,
) -> dict:
    """Run one sub-game against a live opponent server; return a JSON-safe summary."""
    shared, private, config_sha, game_id, game_uid = _load(config_dir)
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
    gateway = HttpOpponentGateway(
        opponent_url,
        router.turn_inbox,
        opponent_token=opponent_token,
        pacer=_build_pacer(opponent_token, config_dir),
    )
    deps = make_deps(
        shared,
        gateway,
        game_uid,
        config_sha,
        seed=private.seed,
        strategy_class=private.strategy.thief_class,
        strategy_weights=private.strategy.weights,
    )
    try:
        result = await SubGameRuntime(deps, machine=machine).run(
            opponent_url=opponent_url, opponent_token=opponent_token
        )
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
