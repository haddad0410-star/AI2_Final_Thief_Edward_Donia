"""Phase 11 wired end-to-end: a real (in-process, fake-gateway) series run
produces all 4 standardized artifacts, internally consistent and reloadable.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from _thief_series_fixtures import CFG_SHA, CONFIG, CONFIG_PATH, THIEF_START, FakeGateway

from thief_peer.services.artifact_models import ConfigArtifact, LogArtifact, ResultArtifact
from thief_peer.services.artifacts import (
    config_filename,
    declaration_filename,
    load_json,
    log_filename,
    result_filename,
)
from thief_peer.services.series_artifacts import write_series_artifacts
from thief_peer.services.series_runtime import run_series
from thief_peer.services.subgame_deps import make_deps
from thief_peer.shared.config_loader import load_private_config, load_shared_config, sha256_hex

CONFIG_DIR = CONFIG_PATH.parent
UID = "22222222-3333-4444-5555-666666666666"
GID = "edward-donia"


def _capture_factory():
    def factory(index: int):
        gw = FakeGateway(opponent_turn={"capture_claim": THIEF_START})
        return make_deps(CONFIG, gw, UID, CFG_SHA, seed=index)

    return factory


def test_write_series_artifacts_produces_all_four_types(tmp_path: Path) -> None:
    series = asyncio.run(run_series(_capture_factory(), num_games=3))
    private = load_private_config(CONFIG_DIR / "game.toml")
    artifacts_dir = tmp_path / "artifacts"

    written = write_series_artifacts(artifacts_dir, CONFIG_DIR, private, GID, UID, CFG_SHA, series)

    # declaration + (config, log) x3 + result
    assert len(written) == 1 + 3 * 2 + 1

    decl_path = artifacts_dir / declaration_filename(GID)
    result_path = artifacts_dir / result_filename(GID)
    assert decl_path.exists()
    assert result_path.exists()
    for n in (1, 2, 3):
        assert (artifacts_dir / config_filename(GID, n)).exists()
        assert (artifacts_dir / log_filename(GID, n)).exists()

    # Every artifact shares the same game_uid.
    uids = {json.loads(p.read_text())["game_uid"] for p in written}
    assert uids == {UID}

    # Each is independently reloadable and schema-valid.
    result = ResultArtifact.from_dict(load_json(result_path))
    assert result.police_total + result.thief_total > 0
    config1 = ConfigArtifact.from_dict(load_json(artifacts_dir / config_filename(GID, 1)))
    assert config1.sub_game_number == 1
    log1 = LogArtifact.from_dict(load_json(artifacts_dir / log_filename(GID, 1)))
    assert log1.audit_verdict == "verified"


def test_write_series_artifacts_reflects_a_shortened_series(tmp_path: Path) -> None:
    """A technical-loss-shortened series (2 of 6 games played) must produce
    exactly 2 config+log artifacts -- never 6, never a fabricated 3rd."""

    def factory(index: int):
        gw = FakeGateway(reject=(index == 2), opponent_turn={"capture_claim": THIEF_START})
        return make_deps(CONFIG, gw, UID, CFG_SHA, seed=index)

    series = asyncio.run(run_series(factory, num_games=6))
    assert len(series.sub_games) == 3
    private = load_private_config(CONFIG_DIR / "game.toml")
    artifacts_dir = tmp_path / "artifacts"

    written = write_series_artifacts(artifacts_dir, CONFIG_DIR, private, GID, UID, CFG_SHA, series)
    assert len(written) == 1 + 3 * 2 + 1
    assert not (artifacts_dir / config_filename(GID, 4)).exists()
    assert not (artifacts_dir / log_filename(GID, 4)).exists()

    result = ResultArtifact.from_dict(load_json(artifacts_dir / result_filename(GID)))
    assert result.agreed is False
    assert len(result.sub_games) == 3


def test_binding_config_sha_matches_disk() -> None:
    assert sha256_hex(CONFIG_PATH) == CFG_SHA
    assert load_shared_config(CONFIG_PATH).network_and_league.num_games == 6
