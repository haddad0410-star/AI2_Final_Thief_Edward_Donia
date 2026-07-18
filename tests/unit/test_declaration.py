"""Phase 5: Step-0 declaration -- required fields, real git hash, honest
missing-hardware behaviour, mismatch detection, tampering, and no secrets."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from thief_peer.domain.declaration import (
    PeerDeclaration,
    build_declaration,
    code_version,
    declaration_mismatches,
    git_commit_hash,
)
from thief_peer.domain.hardware import HardwareInfo, probe_hardware
from thief_peer.domain.sealing import commit_hash, seal, verify_hash
from thief_peer.domain.sealing.payload import SealedTurnPayload
from thief_peer.shared.canonical_json import canonical_json_bytes, canonical_sha256_hex
from thief_peer.shared.config_loader import load_private_config

REPO_ROOT = Path(__file__).resolve().parents[2]
PRIVATE = load_private_config(REPO_ROOT / "config" / "thief" / "game.toml")


def _decl(**over: object) -> PeerDeclaration:
    kwargs: dict = {
        "token_budget": 200000,
        "config_sha256": "c" * 64,
        "repo_root": REPO_ROOT,
        "game_id": "edward-donia-vs-opp",
        "game_uid": "uid-123",
        "now": datetime(2026, 7, 18, tzinfo=UTC),
    }
    kwargs.update(over)
    return build_declaration(PRIVATE, **kwargs)  # type: ignore[arg-type]


def test_required_fields_present() -> None:
    d = _decl()
    assert d.role == "thief"
    assert d.group_id == PRIVATE.game.group_id
    assert d.members == tuple(PRIVATE.game.members)
    assert d.token_budget == 200000
    assert d.code_version == code_version(REPO_ROOT)
    assert d.timestamp.startswith("2026-07-18")


def test_commit_hash_matches_real_git() -> None:
    actual = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert git_commit_hash(REPO_ROOT) == actual
    assert _decl().commit_hash == actual


def test_missing_hardware_field_is_null_plus_status_not_fabricated() -> None:
    hw = HardwareInfo(
        operating_system="TestOS",
        platform_detail="TestOS-1.0",
        python_version="3.11.0",
        cpu_cores=8,
        cpu_model=None,
        cpu_model_status="unavailable on this platform",
        ram_gb=None,
        ram_status="unavailable",
        gpu_model=None,
        vram_gb=None,
        gpu_status="unavailable: no reliable cross-platform GPU/VRAM probe",
    )
    d = _decl(hardware=hw)
    assert d.hardware.gpu_model is None
    assert d.hardware.vram_gb is None
    assert "unavailable" in d.hardware.gpu_status
    assert d.hardware.cpu_model is None
    assert d.hardware.cpu_model_status  # explanatory string present


def test_real_probe_never_fabricates_gpu() -> None:
    hw = probe_hardware()
    assert hw.gpu_model is None and hw.vram_gb is None
    assert hw.operating_system  # OS always known


def test_config_hash_mismatch_detected() -> None:
    d = _decl(config_sha256="a" * 64)
    problems = declaration_mismatches(
        d, expected_config_sha256="b" * 64, expected_group_id=PRIVATE.game.group_id
    )
    assert "config_sha256 mismatch" in problems


def test_identity_mismatch_detected() -> None:
    d = _decl(config_sha256="a" * 64)
    problems = declaration_mismatches(
        d, expected_config_sha256="a" * 64, expected_group_id="some-other-group"
    )
    assert any("identity" in p for p in problems)


def test_schema_version_mismatch_detected() -> None:
    d = _decl(config_sha256="a" * 64)
    problems = declaration_mismatches(
        d,
        expected_config_sha256="a" * 64,
        expected_group_id=PRIVATE.game.group_id,
        expected_schema_version="declaration/99",
    )
    assert "schema version mismatch" in problems


def test_compatible_declaration_has_no_mismatches() -> None:
    d = _decl(config_sha256="a" * 64)
    assert (
        declaration_mismatches(
            d, expected_config_sha256="a" * 64, expected_group_id=PRIVATE.game.group_id
        )
        == ()
    )


def test_declaration_tampering_detected_via_sealing() -> None:
    d = _decl(config_sha256="a" * 64)
    canonical = d.to_canonical_dict()
    published = canonical_sha256_hex(canonical)
    assert verify_hash(canonical, published) is True
    tampered = dict(canonical)
    tampered["commit_hash"] = "0" * 40
    assert verify_hash(tampered, published) is False


def test_declaration_can_be_sealed_like_a_turn() -> None:
    d = _decl()
    payload = SealedTurnPayload(
        step=0,
        role="thief",
        sub_game_number=1,
        state=canonical_sha256_hex(d.to_canonical_dict()),
        move=None,
        intent="truth",
        hint="declaration",
        scent_digest="0" * 8,
        timestamp=d.timestamp,
        nonce="n" * 64,
        config_sha256=d.config_sha256,
    )
    assert seal(payload).recompute_matches() is True
    assert commit_hash(payload)


def test_no_credentials_in_serialized_declaration() -> None:
    blob = canonical_json_bytes(_decl().to_canonical_dict()).decode("utf-8").lower()
    for needle in ("secret", "password", "api_key", "token.json", "credentials.json"):
        assert needle not in blob, f"{needle!r} present in declaration"
    # 'token_budget' is a legitimate FIELD NAME, not a secret value.
    assert "token_budget" in canonical_json_bytes(_decl().to_canonical_dict()).decode("utf-8")
