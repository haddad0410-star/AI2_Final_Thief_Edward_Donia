"""Batch 4A CLI handlers (``peer``, ``replay``), split out of ``__main__.py``
to keep it under the 150-meaningful-line cap. Still argument-parsing/
dispatch only -- no business logic lives here either.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def peer(args: argparse.Namespace, run_series) -> int:
    if not args.gui:  # default, and explicit --no-gui, both land here
        return run_series(args)
    from thief_peer.sdk.gui_runner import run_gui
    from thief_peer.sdk.public_mode import PublicModeError, resolve_public_tokens

    try:
        public_token, opponent_token = resolve_public_tokens(args.public)
    except PublicModeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    artifacts_dir = Path(args.artifacts_dir) if args.artifacts_dir else None
    return run_gui(
        Path(args.config_dir),
        args.opponent_url,
        args.smoke,
        artifacts_dir,
        public_token=public_token,
        opponent_token=opponent_token,
    )


def replay(args: argparse.Namespace) -> int:
    from thief_peer.gui.replay_view_model import build_replay_view

    police_dir, thief_dir = Path(args.police_artifacts), Path(args.thief_artifacts)
    if not args.gui:
        model = build_replay_view(police_dir, thief_dir)
        print(f"REPLAY VERDICT: {model.verdict}")
        print(f"FULL_BILATERAL_VERIFICATION={str(model.full_bilateral_verification).lower()}")
        print(
            f"thief: independently_verified={model.thief.independently_verified} verdict={model.thief.verdict}"
        )
        print(
            f"police: independently_verified={model.police.independently_verified} verdict={model.police.verdict}"
        )
        for f in (*model.thief.findings, *model.police.findings):
            print(f"  - {f}")
        return 0 if model.verification_ok else 2
    from thief_peer.gui.tk_replay_app import ReplayApp

    app = ReplayApp(police_dir, thief_dir)
    ok = app.model.verification_ok
    app.run()
    return 0 if ok else 2
