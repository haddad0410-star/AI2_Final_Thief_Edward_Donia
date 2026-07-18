"""CLI entry point.

Commands:
- ``negotiate-smoke``   : Batch 1 minimal real FastMCP negotiation slice.
- ``run-subgame``       : run one sub-game against a live opponent (Phase 9).
- ``run-series``        : run the full 6-game series (``--smoke`` = 1 game) (Phase 10).
- ``verify-replay``     : headless artifact verifier, VERIFIED/TAMPERED (Phase 12).
- ``show-status``       : print the locally-parsed config (no network calls).

Business logic lives in the SDK/services layers; this file only parses args,
dispatches, and reports a clear exit code. A Ctrl+C (SIGINT) during any
command reaches the SDK layer's own ``try/finally`` (server.stop() always
runs, per infrastructure/server_lifecycle.py's module docstring), and is
reported here as a clean message + exit code 130, never a raw traceback.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from thief_peer.domain.roles import Role
from thief_peer.sdk.game_runner import (
    print_summary,
    run_series_headless,
    run_subgame_headless,
    summary_exit_code,
)
from thief_peer.sdk.negotiation_runner import run_negotiation_smoke
from thief_peer.services.replay_verifier import verify_replay
from thief_peer.shared.config_loader import load_private_config, load_shared_config, sha256_hex
from thief_peer.shared.errors import ConfigError

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "thief"


def _negotiate_smoke() -> int:
    summary = asyncio.run(run_negotiation_smoke(Role.THIEF, CONFIG_DIR))
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("outcome") == "negotiated" else 1


def _run_subgame(args: argparse.Namespace) -> int:
    summary = asyncio.run(run_subgame_headless(Path(args.config_dir), args.opponent_url))
    print_summary(summary)
    return summary_exit_code(summary)


def _run_series(args: argparse.Namespace) -> int:
    artifacts_dir = Path(args.artifacts_dir) if args.artifacts_dir else None
    summary = asyncio.run(
        run_series_headless(
            Path(args.config_dir), args.opponent_url, smoke=args.smoke, artifacts_dir=artifacts_dir
        )
    )
    print_summary(summary)
    return summary_exit_code(summary)


def _verify_replay(args: argparse.Namespace) -> int:
    report = verify_replay(Path(args.artifacts))
    print(report.verdict)
    for finding in report.findings:
        print(f"  - {finding}")
    return 0 if report.ok else 2


def _show_status(args: argparse.Namespace) -> int:
    config_dir = Path(args.config_dir)
    try:
        shared = load_shared_config(config_dir / "game.json")
        private = load_private_config(config_dir / "game.toml")
    except (ConfigError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    status = {
        "ok": True,
        "config_dir": str(config_dir),
        "config_sha256": sha256_hex(config_dir / "game.json"),
        "num_games": shared.network_and_league.num_games,
        "my_port": private.network.my_port,
        "opponent_url": private.network.opponent_url,
        "group_id": private.game.group_id,
        "strategy_class": private.strategy.thief_class,
    }
    print(json.dumps(status, indent=2))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thief_peer")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("negotiate-smoke", help="Batch 1 minimal FastMCP negotiation slice")

    default_url = "http://127.0.0.1:8901/mcp"
    sub = subparsers.add_parser("run-subgame", help="Run one sub-game vs a live opponent")
    sub.add_argument("--headless", action="store_true", help="headless (no GUI); default mode")
    sub.add_argument("--config-dir", default=str(CONFIG_DIR))
    sub.add_argument("--opponent-url", default=default_url)

    series = subparsers.add_parser("run-series", help="Run the full 6-game series")
    series.add_argument("--headless", action="store_true", help="headless (no GUI); default mode")
    series.add_argument("--smoke", action="store_true", help="single-game SMOKE TEST ONLY")
    series.add_argument("--config-dir", default=str(CONFIG_DIR))
    series.add_argument("--opponent-url", default=default_url)
    series.add_argument(
        "--artifacts-dir", default=None, help="write the 4 standardized JSON artifacts here"
    )

    verify = subparsers.add_parser("verify-replay", help="Verify an artifact directory")
    verify.add_argument("--artifacts", required=True, help="directory of JSON artifacts")

    status = subparsers.add_parser("show-status", help="Print the locally-parsed config")
    status.add_argument("--config-dir", default=str(CONFIG_DIR))
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    try:
        if args.command == "negotiate-smoke":
            sys.exit(_negotiate_smoke())
        if args.command == "run-subgame":
            sys.exit(_run_subgame(args))
        if args.command == "run-series":
            sys.exit(_run_series(args))
        if args.command == "verify-replay":
            sys.exit(_verify_replay(args))
        if args.command == "show-status":
            sys.exit(_show_status(args))
        raise NotImplementedError(f"command {args.command!r} is not implemented yet")
    except KeyboardInterrupt:
        print("\ninterrupted: shutting down", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
