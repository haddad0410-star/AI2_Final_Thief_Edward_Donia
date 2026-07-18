"""Build the JSON artifact models from live runtime results (Batch 2, Phase 11).
Independent implementation (no import of the Police repository)."""

from __future__ import annotations

from typing import Any

from thief_peer.domain.captures import SubGameResult
from thief_peer.domain.sealing import AuditReport, SealedRecord
from thief_peer.services.artifact_models import ConfigArtifact, LogArtifact, ResultArtifact
from thief_peer.services.series_runtime import SeriesResult

_WINNER = {SubGameResult.CAPTURE: "police", SubGameResult.SURVIVAL: "thief"}


def build_config_artifact(
    game_uid: str, game_id: str, sub_game_number: int, config_sha256: str, terms: dict
) -> ConfigArtifact:
    """Config artifact for one sub-game (agreed terms + hash)."""
    return ConfigArtifact(game_uid, game_id, sub_game_number, config_sha256, terms)


def build_log_artifact(
    game_uid: str,
    game_id: str,
    sub_game_number: int,
    records: tuple[SealedRecord, ...],
    audit: AuditReport,
) -> LogArtifact:
    """Log artifact: sealed step records (nonces revealed) + audit verdict."""
    steps: list[dict[str, Any]] = [
        {**record.payload.to_canonical_dict(), "commit_hash": record.commit_hash}
        for record in records
    ]
    return LogArtifact(
        game_uid=game_uid,
        game_id=game_id,
        sub_game_number=sub_game_number,
        steps=steps,
        audit_verdict=audit.outcome.value,
        audit_reason=audit.reason,
    )


def build_result_artifact(
    game_uid: str,
    game_id: str,
    git_commit: str,
    group_id: str,
    config_sha256: str,
    series: SeriesResult,
) -> ResultArtifact:
    """Whole-series result artifact with per-sub-game scores + final agreement."""
    sub_games = [
        {
            "sub_game_number": r.sub_game_number,
            "result": r.result.value,
            "winner": _WINNER.get(r.result),
            "police_score": r.police_score,
            "thief_score": r.thief_score,
            "steps": r.steps_taken,
            "audit_ok": r.audit_verified,
        }
        for r in series.sub_games
    ]
    agreed = series.terminated_reason == "completed"
    return ResultArtifact(
        game_uid=game_uid,
        game_id=game_id,
        git_commit=git_commit,
        group_id=group_id,
        config_sha256=config_sha256,
        sub_games=sub_games,
        police_total=series.police_total,
        thief_total=series.thief_total,
        agreement_status=("completed" if agreed else series.terminated_reason),
        agreed=agreed,
    )
