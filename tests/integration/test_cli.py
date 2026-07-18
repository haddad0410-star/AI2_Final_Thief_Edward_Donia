"""CLI regression tests (Batch 2, Phase 9-12 wiring, session recovery step B
Task 7). Real subprocess invocations of ``python -m thief_peer`` for
argparse-level behavior (help, unknown command, exit codes), plus direct
``main()`` calls for scenarios that need to inject a failure (interruption).
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest
from _thief_series_fixtures import CFG_SHA, CONFIG, CONFIG_PATH, THIEF_START, FakeGateway

import thief_peer.__main__ as cli
from thief_peer.services.series_artifacts import write_series_artifacts
from thief_peer.services.series_runtime import run_series
from thief_peer.services.subgame_deps import make_deps
from thief_peer.shared.config_loader import load_private_config

CONFIG_DIR = CONFIG_PATH.parent
UID = "33333333-4444-5555-6666-777777777777"
GID = "edward-donia"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "thief_peer", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_help_exits_zero() -> None:
    result = _run_cli("--help")
    assert result.returncode == 0
    assert "run-subgame" in result.stdout
    assert "run-series" in result.stdout
    assert "verify-replay" in result.stdout
    assert "show-status" in result.stdout


def test_unknown_command_exits_nonzero() -> None:
    result = _run_cli("not-a-real-command")
    assert result.returncode != 0


def test_show_status_valid_command_dispatch() -> None:
    result = _run_cli("show-status", "--config-dir", str(CONFIG_DIR))
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["num_games"] == 6
    assert data["config_sha256"] == CFG_SHA


def test_show_status_missing_config_reports_error_not_crash(tmp_path: Path) -> None:
    empty_dir = tmp_path / "no-config-here"
    empty_dir.mkdir()
    result = _run_cli("show-status", "--config-dir", str(empty_dir))
    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert "error" in data


def test_verify_replay_invalid_artifact_path_reports_tampered(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    result = _run_cli("verify-replay", "--artifacts", str(missing))
    assert result.returncode == 2
    assert "TAMPERED" in result.stdout


def test_verify_replay_success_on_real_generated_artifacts(tmp_path: Path) -> None:
    def factory(index: int):
        gw = FakeGateway(opponent_turn={"capture_claim": THIEF_START})
        return make_deps(CONFIG, gw, UID, CFG_SHA, seed=index)

    series = asyncio.run(run_series(factory, num_games=2))
    private = load_private_config(CONFIG_DIR / "game.toml")
    artifacts_dir = tmp_path / "artifacts"
    write_series_artifacts(artifacts_dir, CONFIG_DIR, private, GID, UID, CFG_SHA, series)

    result = _run_cli("verify-replay", "--artifacts", str(artifacts_dir))
    assert result.returncode == 0
    assert result.stdout.strip().startswith("VERIFIED")


def test_verify_replay_failure_on_tampered_artifacts(tmp_path: Path) -> None:
    def factory(index: int):
        gw = FakeGateway(opponent_turn={"capture_claim": THIEF_START})
        return make_deps(CONFIG, gw, UID, CFG_SHA, seed=index)

    series = asyncio.run(run_series(factory, num_games=1))
    private = load_private_config(CONFIG_DIR / "game.toml")
    artifacts_dir = tmp_path / "artifacts"
    written = write_series_artifacts(artifacts_dir, CONFIG_DIR, private, GID, UID, CFG_SHA, series)
    result_path = next(p for p in written if p.name.startswith("result_"))
    data = json.loads(result_path.read_text())
    data["thief_total"] = 999999
    result_path.write_text(json.dumps(data))

    result = _run_cli("verify-replay", "--artifacts", str(artifacts_dir))
    assert result.returncode == 2
    assert "TAMPERED" in result.stdout


def test_interruption_exits_130(monkeypatch) -> None:
    def _raise_keyboard_interrupt(_args):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_show_status", _raise_keyboard_interrupt)
    monkeypatch.setattr(sys, "argv", ["thief_peer", "show-status"])
    with pytest.raises(SystemExit) as exc_info:
        cli.main()
    assert exc_info.value.code == 130
