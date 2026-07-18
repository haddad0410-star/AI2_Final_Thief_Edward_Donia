"""Assemble and save the four standardized JSON artifacts for a completed
(or technical-loss-shortened) series (Batch 2, Phase 11).

Reuses the model/save layer (``artifact_models.py``, ``artifact_builders.py``,
``artifacts.py``); this module is purely the orchestration wiring them
together with the real declaration and per-sub-game sealed records.
Independent implementation (no import of the Police repository).
"""

from __future__ import annotations

import json
from pathlib import Path

from thief_peer.domain.declaration import build_declaration, git_commit_hash
from thief_peer.domain.sealing import audit_sealed_records
from thief_peer.services.artifact_builders import (
    build_config_artifact,
    build_log_artifact,
    build_result_artifact,
)
from thief_peer.services.artifacts import (
    config_filename,
    declaration_filename,
    log_filename,
    result_filename,
    save_artifact,
)
from thief_peer.services.series_runtime import SeriesResult
from thief_peer.shared.private_config import PrivateGameConfig

REPO_ROOT = Path(__file__).resolve().parents[3]


def write_series_artifacts(
    artifacts_dir: Path,
    config_dir: Path,
    private: PrivateGameConfig,
    game_id: str,
    game_uid: str,
    config_sha256: str,
    series: SeriesResult,
) -> list[Path]:
    """Write one declaration, one config+log per sub-game actually played,
    and one result artifact; return every path written. Reflects exactly
    what happened, including a series that ended early on a technical loss
    -- never more config/log files than sub-games actually played."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    terms = json.loads((config_dir / "game.json").read_text(encoding="utf-8"))
    commit = git_commit_hash(REPO_ROOT)
    token_budget = terms.get("network_and_league", {}).get("token_budget_per_series", 0)
    written: list[Path] = []

    declaration = build_declaration(
        private, token_budget, config_sha256, REPO_ROOT, game_id=game_id, game_uid=game_uid
    )
    written.append(save_artifact(declaration, artifacts_dir / declaration_filename(game_id)))

    for record, run_result in zip(series.sub_games, series.run_results, strict=True):
        n = record.sub_game_number
        config_artifact = build_config_artifact(game_uid, game_id, n, config_sha256, terms)
        written.append(save_artifact(config_artifact, artifacts_dir / config_filename(game_id, n)))

        audit = audit_sealed_records(run_result.records)
        log_artifact = build_log_artifact(game_uid, game_id, n, run_result.records, audit)
        written.append(save_artifact(log_artifact, artifacts_dir / log_filename(game_id, n)))

    result_artifact = build_result_artifact(
        game_uid, game_id, commit, private.game.group_id, config_sha256, series
    )
    written.append(save_artifact(result_artifact, artifacts_dir / result_filename(game_id)))
    return written
