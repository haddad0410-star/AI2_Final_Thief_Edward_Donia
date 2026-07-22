"""Batch 4A Task 7/8, updated Batch 4B Task 3/4: headless tests for the
graphical replay viewer's data layer and playback navigation. No Tkinter
import anywhere in this file. Uses the SAME real artifact-writing helpers
as ``tests/security/test_replay_verifier.py`` (Thief's own crypto module)
so both sides' "clean bundle" fixtures are genuinely sealed/hashed, not
hand-faked -- since Batch 4B Task 3 unified the sealed field set into one
``commitment/1`` schema, a role="police" payload can be legitimately built
and sealed with THIS repo's own crypto module (exercising the same code
path a real cross-repo Police ``commitment/1`` artifact would hit) without
importing ``police_peer``.
"""

from __future__ import annotations

import json
from pathlib import Path

from thief_peer.domain.captures import SubGameResult
from thief_peer.domain.sealing import AuditOutcome, AuditReport, SealedTurnPayload, seal
from thief_peer.gui.replay_playback import PlaybackState
from thief_peer.gui.replay_view_model import build_replay_view
from thief_peer.services.artifact_builders import build_log_artifact, build_result_artifact
from thief_peer.services.artifact_models import ConfigArtifact
from thief_peer.services.artifacts import (
    config_filename,
    log_filename,
    result_filename,
    save_artifact,
)
from thief_peer.services.series_runtime import SeriesResult, SeriesSubGameRecord
from thief_peer.shared.canonical_json import canonical_json_bytes
from thief_peer.shared.config_loader import sha256_hex

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "thief"
UID = "abcabcab-1111-2222-3333-444444444444"
GID = "edward-donia"
N_GAMES = 2
STEPS_PER_GAME = 3


def _terms() -> dict:
    with open(CONFIG_DIR / "game.json", encoding="utf-8") as handle:
        return json.load(handle)


def _payload(role: str, sub_game: int, step: int, *, col_offset: int = 0) -> SealedTurnPayload:
    police_only = role == "police"
    return SealedTurnPayload(
        step=step,
        role=role,
        sub_game_number=sub_game,
        position=(step, col_offset),
        move="E" if role == "thief" else "S",
        barrier_placed=(3, 3) if police_only and step == 1 else None,
        capture_claim=(step, col_offset) if police_only else None,
        claim_response=None if police_only else True,
        win_claim=False,
        intent="truth",
        hint="east looks fine" if role == "thief" else "south",
        scent_digest="d" * 64,
        scent_grid=((0.0, 0.0), (0.0, 0.0)),
        timestamp="2026-07-18T00:00:00+00:00",
        nonce=f"{role}{sub_game:030x}{step:032x}",
        config_sha256=sha256_hex(CONFIG_DIR / "game.json"),
    )


def _write_bundle(directory: Path, role: str, winner: str, *, col_offset: int = 0) -> None:
    terms = _terms()
    config_sha = sha256_hex(CONFIG_DIR / "game.json")
    for n in range(1, N_GAMES + 1):
        recs = tuple(
            seal(_payload(role, n, s, col_offset=col_offset)) for s in range(STEPS_PER_GAME)
        )
        save_artifact(
            ConfigArtifact(UID, GID, n, config_sha, terms), directory / config_filename(GID, n)
        )
        log = build_log_artifact(
            UID, GID, n, recs, AuditReport(AuditOutcome.VERIFIED, (), (), "ok")
        )
        save_artifact(log, directory / log_filename(GID, n))
    sub_records = tuple(
        SeriesSubGameRecord(n, SubGameResult.CAPTURE, 20, 5, STEPS_PER_GAME, True)
        for n in range(1, N_GAMES + 1)
    )
    series = SeriesResult(sub_records, 20 * N_GAMES, 5 * N_GAMES, "completed", None)
    result = build_result_artifact(UID, GID, "deadbeef", GID, config_sha, series)
    save_artifact(result, directory / result_filename(GID))
    decl = {"schema_version": "declaration/1", "game_uid": UID, "game_id": GID, "role": role}
    (directory / f"declaration_{GID}.json").write_bytes(canonical_json_bytes(decl) + b"\n")


def _write_thief_bundle(directory: Path) -> None:
    _write_bundle(directory, "thief", "police", col_offset=1)


def _write_police_bundle(directory: Path) -> None:
    _write_bundle(directory, "police", "police", col_offset=0)


def _write_legacy_police_bundle(directory: Path) -> None:
    """A real, pre-Batch-4B Police-shaped bundle (nested ``state`` dict,
    ``commit-reveal/2``) -- preserved specifically to test the legacy
    fallback path, since Batch 4B Task 3 no longer produces this shape for
    NEWLY sealed records."""
    terms = _terms()
    config_sha = sha256_hex(CONFIG_DIR / "game.json")
    for n in range(1, N_GAMES + 1):
        steps = [
            {
                "step": s,
                "role": "police",
                "sub_game_number": n,
                "state": {"position": [s, 0]},
                "move": "S",
                "hint": "south",
                "barrier_placed": [3, 3] if s == 1 else None,
                "capture_claim": [s, 0],
                "claim_response": None,
                "win_claim": False,
                "commit_hash": "a" * 64,
                "nonce": "b" * 64,
                "timestamp": "2026-07-18T00:00:00+00:00",
                "schema_version": "commit-reveal/2",
                "scent_digest": "c" * 64,
                "scent_grid": [[0.0, 0.0], [0.0, 0.0]],
                "intent": "truth",
            }
            for s in range(STEPS_PER_GAME)
        ]
        (directory / config_filename(GID, n)).write_text(
            json.dumps(
                {
                    "game_uid": UID,
                    "game_id": GID,
                    "sub_game_number": n,
                    "config_sha256": config_sha,
                    "terms": terms,
                }
            )
        )
        (directory / log_filename(GID, n)).write_text(
            json.dumps(
                {
                    "game_uid": UID,
                    "game_id": GID,
                    "sub_game_number": n,
                    "steps": steps,
                    "audit_verdict": "verified",
                    "audit_reason": "ok",
                }
            )
        )
    sub_games = [
        {
            "sub_game_number": n,
            "result": "capture",
            "winner": "police",
            "police_score": 20,
            "thief_score": 5,
            "steps": STEPS_PER_GAME,
            "audit_ok": True,
        }
        for n in range(1, N_GAMES + 1)
    ]
    (directory / result_filename(GID)).write_text(
        json.dumps(
            {
                "game_uid": UID,
                "game_id": GID,
                "config_sha256": config_sha,
                "sub_games": sub_games,
                "police_total": 40,
                "thief_total": 10,
            }
        )
    )
    (directory / f"declaration_{GID}.json").write_text(
        json.dumps(
            {"schema_version": "declaration/1", "game_uid": UID, "game_id": GID, "role": "police"}
        )
    )


def _model(tmp_path: Path):
    police_dir, thief_dir = tmp_path / "police", tmp_path / "thief"
    police_dir.mkdir()
    thief_dir.mkdir()
    _write_police_bundle(police_dir)
    _write_thief_bundle(thief_dir)
    return build_replay_view(police_dir, thief_dir)


def test_valid_six_sub_game_like_set_fully_bilaterally_verified(tmp_path) -> None:
    model = _model(tmp_path)
    assert model.verdict == "VERIFIED"
    assert model.verification_ok is True
    assert model.full_bilateral_verification is True
    assert len(model.sub_games) == N_GAMES


def test_both_sides_independently_verified(tmp_path) -> None:
    model = _model(tmp_path)
    assert model.police.independently_verified is True
    assert model.police.verdict == "VERIFIED"
    assert model.thief.independently_verified is True
    assert model.thief.verdict == "VERIFIED"


def test_legacy_opponent_schema_still_uses_documented_fallback(tmp_path) -> None:
    police_dir, thief_dir = tmp_path / "police", tmp_path / "thief"
    police_dir.mkdir()
    thief_dir.mkdir()
    _write_legacy_police_bundle(police_dir)
    _write_thief_bundle(thief_dir)
    model = build_replay_view(police_dir, thief_dir)
    assert model.police.independently_verified is False
    assert "LEGACY_SCHEMA" in model.police.verdict
    assert model.thief.independently_verified is True
    assert model.full_bilateral_verification is False


def test_tampered_police_commitment_is_detected_by_thief(tmp_path) -> None:
    police_dir, thief_dir = tmp_path / "police", tmp_path / "thief"
    police_dir.mkdir()
    thief_dir.mkdir()
    _write_police_bundle(police_dir)
    _write_thief_bundle(thief_dir)
    data = json.loads((police_dir / log_filename(GID, 1)).read_text())
    data["steps"][0]["move"] = "N"
    (police_dir / log_filename(GID, 1)).write_text(json.dumps(data))
    model = build_replay_view(police_dir, thief_dir)
    assert model.police.independently_verified is True
    assert model.police.verdict == "TAMPERED"
    assert model.full_bilateral_verification is False


def test_both_true_paths_present(tmp_path) -> None:
    model = _model(tmp_path)
    sg = model.sub_games[0]
    assert sg.thief_steps[0].position == (0, 1)
    assert sg.police_steps[0].position == (0, 0)


def test_barriers_present(tmp_path) -> None:
    model = _model(tmp_path)
    assert model.sub_games[0].barriers == ((3, 3),)


def test_score_display(tmp_path) -> None:
    model = _model(tmp_path)
    assert model.sub_games[0].police_score == 20
    assert model.sub_games[0].thief_score == 5


def test_sub_game_selection(tmp_path) -> None:
    model = _model(tmp_path)
    playback = PlaybackState()
    playback.select(model, 1)
    assert playback.sub_game_index == 1
    assert playback.step == 0


def test_playback_order_and_step_navigation(tmp_path) -> None:
    model = _model(tmp_path)
    playback = PlaybackState()
    playback.next(model)
    playback.next(model)
    assert playback.step == 2
    playback.prev()
    assert playback.step == 1
    playback.jump_end(model)
    assert playback.step == playback.max_step(model)
    playback.jump_start()
    assert playback.step == 0


def test_pause_resume(tmp_path) -> None:
    playback = PlaybackState()
    assert playback.playing is False
    playback.toggle_play()
    assert playback.playing is True
    playback.toggle_play()
    assert playback.playing is False


def test_playback_tick_advances_and_stops_at_end(tmp_path) -> None:
    model = _model(tmp_path)
    playback = PlaybackState()
    playback.playing = True
    advanced = playback.advance_if_playing(model)
    assert advanced is True
    playback.step = playback.max_step(model)
    advanced_at_end = playback.advance_if_playing(model)
    assert advanced_at_end is False
    assert playback.playing is False


def test_missing_log_is_reflected_as_empty_steps(tmp_path) -> None:
    police_dir, thief_dir = tmp_path / "police", tmp_path / "thief"
    police_dir.mkdir()
    thief_dir.mkdir()
    _write_police_bundle(police_dir)
    _write_thief_bundle(thief_dir)
    (thief_dir / log_filename(GID, 2)).unlink()
    model = build_replay_view(police_dir, thief_dir)
    assert model.verification_ok is False
    assert any("missing" in f.lower() or "count" in f.lower() for f in model.thief.findings)


def test_duplicate_log_is_detected(tmp_path) -> None:
    police_dir, thief_dir = tmp_path / "police", tmp_path / "thief"
    police_dir.mkdir()
    thief_dir.mkdir()
    _write_police_bundle(police_dir)
    _write_thief_bundle(thief_dir)
    data = json.loads((thief_dir / log_filename(GID, 2)).read_text())
    data["sub_game_number"] = 1
    (thief_dir / log_filename(GID, 2)).write_text(json.dumps(data))
    model = build_replay_view(police_dir, thief_dir)
    assert model.verification_ok is False
    assert any("duplicate" in f.lower() for f in model.thief.findings)


def test_wrong_game_uid_is_detected(tmp_path) -> None:
    police_dir, thief_dir = tmp_path / "police", tmp_path / "thief"
    police_dir.mkdir()
    thief_dir.mkdir()
    _write_police_bundle(police_dir)
    _write_thief_bundle(thief_dir)
    data = json.loads((thief_dir / result_filename(GID)).read_text())
    data["game_uid"] = "different-uid"
    (thief_dir / result_filename(GID)).write_text(json.dumps(data))
    model = build_replay_view(police_dir, thief_dir)
    assert model.verification_ok is False
    assert any("game_uid" in f for f in model.thief.findings)


def test_wrong_config_hash_is_detected(tmp_path) -> None:
    police_dir, thief_dir = tmp_path / "police", tmp_path / "thief"
    police_dir.mkdir()
    thief_dir.mkdir()
    _write_police_bundle(police_dir)
    _write_thief_bundle(thief_dir)
    data = json.loads((thief_dir / config_filename(GID, 1)).read_text())
    data["config_sha256"] = "0" * 64
    (thief_dir / config_filename(GID, 1)).write_text(json.dumps(data))
    model = build_replay_view(police_dir, thief_dir)
    assert model.verification_ok is False


def test_mismatched_score_is_detected(tmp_path) -> None:
    police_dir, thief_dir = tmp_path / "police", tmp_path / "thief"
    police_dir.mkdir()
    thief_dir.mkdir()
    _write_police_bundle(police_dir)
    _write_thief_bundle(thief_dir)
    data = json.loads((thief_dir / result_filename(GID)).read_text())
    data["sub_games"][0]["police_score"] = 999
    (thief_dir / result_filename(GID)).write_text(json.dumps(data))
    model = build_replay_view(police_dir, thief_dir)
    assert model.verification_ok is False


def test_no_dependency_on_live_process_memory(tmp_path) -> None:
    """build_replay_view takes only a Path -- it never reads any
    in-process runtime object, module-level game state, or gui_sink."""
    import inspect

    from thief_peer.gui.replay_view_model import build_replay_view as f

    params = inspect.signature(f).parameters
    assert set(params) == {"police_dir", "thief_dir"}
    for p in params.values():
        assert p.annotation in (Path, "Path")
