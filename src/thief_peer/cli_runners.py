"""``run-subgame``/``run-series`` CLI handlers -- split out of
``__main__.py`` (Gate A1's ``--public`` token resolution pushed that file
over the 150-line cap).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from thief_peer.sdk.game_runner import print_summary, run_series_headless, summary_exit_code
from thief_peer.sdk.public_mode import PublicModeError, resolve_public_tokens
from thief_peer.sdk.subgame_runner import run_subgame_headless


def run_subgame(args: argparse.Namespace) -> int:
    try:
        public_token, opponent_token = resolve_public_tokens(args.public)
    except PublicModeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    summary = asyncio.run(
        run_subgame_headless(
            Path(args.config_dir),
            args.opponent_url,
            public_token=public_token,
            opponent_token=opponent_token,
        )
    )
    print_summary(summary)
    return summary_exit_code(summary)


def run_series(args: argparse.Namespace) -> int:
    try:
        public_token, opponent_token = resolve_public_tokens(args.public)
    except PublicModeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    artifacts_dir = Path(args.artifacts_dir) if args.artifacts_dir else None
    summary = asyncio.run(
        run_series_headless(
            Path(args.config_dir),
            args.opponent_url,
            smoke=args.smoke,
            artifacts_dir=artifacts_dir,
            public_token=public_token,
            opponent_token=opponent_token,
        )
    )
    print_summary(summary)
    return summary_exit_code(summary)
