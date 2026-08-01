"""Phase 5: Step-0 declaration -- required fields, real git hash, honest
missing-hardware behaviour, mismatch detection, tampering, and no secrets.

Canonical schema frozen in session recovery step C (declaration/2,
docs/schemas/declaration.schema.json, resolving risk #14). Cross-repository
byte-identical-fixture and schema-SHA-256 comparisons live in
integration_lab/scripts/compare_declaration_schemas.py, not here (a single
repo's tests cannot import the sibling repo).
"""

from __future__ import annotations

import dataclasses
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from thief_peer.domain.declaration import PeerDeclaration
from thief_peer.domain.declaration_builder import (
    DeclarationContext,
    build_declaration,
    code_version,
    git_commit_hash,
)
from thief_peer.domain.declaration_checks import declaration_mismatches
from thief_peer.domain.hardware import HardwareInfo, probe_hardware
from thief_peer.shared.canonical_json import canonical_json_bytes
from thief_peer.shared.config_loader import load_private_config
from thief_peer.shared.errors import SchemaValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
PRIVATE = load_private_config(REPO_ROOT / "config" / "thief" / "game.toml")

_HW = HardwareInfo(
    operating_system="TestOS",
    platform_detail="TestOS-1.0",
    python_version="3.11.0",
    cpu_model="Test CPU 9000",
    cpu_model_status="detected",
    cpu_cores=8,
    ram_gb=16.0,
    ram_status="detected via sysconf",
    gpu_model=None,
    gpu_available=False,
    gpu_status="not detected",
    vram_gb=None,
    vram_status="not detected",
)


def _context(**over: object) -> DeclarationContext:
    base = {
        "role": "thief",
        "game_id": "edward-donia-vs-opp",
        "game_uid": "uid-123",
        "token_budget": 200000,
        "num_sub_games": 6,
        "config_sha256": "c" * 64,
        "my_mcp_url": "http://127.0.0.1:8902/mcp",
        "opponent_mcp_url": "http://127.0.0.1:8901/mcp",
    }
    base.update(over)
    return DeclarationContext(**base)  # type: ignore[arg-type]


def _decl(*, hardware: HardwareInfo | None = _HW, **context_over: object) -> PeerDeclaration:
    return build_declaration(
        PRIVATE,
        _context(**context_over),
        REPO_ROOT,
        hardware=hardware,
        now=datetime(2026, 7, 18, tzinfo=UTC),
    )


def test_required_fields_present() -> None:
    d = _decl()
    data = d.to_dict()
    for key in (
        "schema_version",
        "game_id",
        "game_uid",
        "role",
        "group_id",
        "group_name",
        "members",
        "police_repository",
        "thief_repository",
        "police_mcp_url",
        "thief_mcp_url",
        "timezone",
        "timestamp",
        "token_budget",
        "num_sub_games",
        "shared_config_sha256",
        "code_version",
        "git_commit",
        "strategy_class",
        "banter_provider",
        "hardware",
        "content_sha256",
    ):
        assert key in data
    assert d.role == "thief"
    assert d.schema_version == "declaration/2"
    assert d.group_id == PRIVATE.game.group_id
    assert d.members == tuple(PRIVATE.game.members)
    assert d.token_budget == 200000
    assert d.code_version == code_version(REPO_ROOT)
    assert d.timestamp.startswith("2026-07-18")


def test_round_trip_through_from_dict() -> None:
    d = _decl()
    reloaded = PeerDeclaration.from_dict(d.to_dict())
    assert reloaded == d


def test_role_specific_mcp_url_mapping() -> None:
    """The caller's own URL and the opponent's URL are placed under the
    correct police_mcp_url/thief_mcp_url key based on `role`."""
    d = _decl(
        role="thief",
        my_mcp_url="http://127.0.0.1:8902/mcp",
        opponent_mcp_url="http://127.0.0.1:8901/mcp",
    )
    assert d.thief_mcp_url == "http://127.0.0.1:8902/mcp"
    assert d.police_mcp_url == "http://127.0.0.1:8901/mcp"


def test_missing_field_rejected() -> None:
    d = _decl()
    data = d.to_dict()
    del data["police_mcp_url"]
    with pytest.raises(SchemaValidationError, match="missing required fields"):
        PeerDeclaration.from_dict(data)


def test_wrong_type_rejected_by_validate() -> None:
    d = _decl()
    bad = dataclasses.replace(d, num_sub_games=0)
    with pytest.raises(SchemaValidationError, match="num_sub_games"):
        bad.validate()


def test_wrong_schema_version_rejected() -> None:
    d = _decl()
    data = d.to_dict()
    data["schema_version"] = "declaration/1"
    with pytest.raises(SchemaValidationError, match="schema_version"):
        PeerDeclaration.from_dict(data)


def test_wrong_game_uid_survives_round_trip_for_caller_comparison() -> None:
    d = _decl(game_uid="different-uid")
    reloaded = PeerDeclaration.from_dict(d.to_dict())
    assert reloaded.game_uid == "different-uid"


def test_commit_hash_matches_real_git() -> None:
    """When ``.git`` exists, must match the real HEAD exactly. When it
    doesn't (a clean-extracted review ZIP, which deliberately excludes
    ``.git``), must match the packaged ``BUILD_COMMIT`` file instead --
    never silently skipped either way."""
    if (REPO_ROOT / ".git").exists():
        actual = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert git_commit_hash(REPO_ROOT) == actual
        assert _decl().git_commit == actual
        return
    build_commit = REPO_ROOT / "BUILD_COMMIT"
    assert build_commit.exists(), "no .git and no BUILD_COMMIT -- commit provenance unverifiable"
    expected = build_commit.read_text(encoding="utf-8").strip()
    assert git_commit_hash(REPO_ROOT) == expected
    assert _decl().git_commit == expected


def test_missing_hardware_field_is_null_plus_status_not_fabricated() -> None:
    hw = dataclasses.replace(
        _HW, cpu_model=None, cpu_model_status="unavailable on this platform", ram_gb=None
    )
    d = _decl(hardware=hw)
    assert d.hardware.gpu_model is None
    assert d.hardware.vram_gb is None
    assert d.hardware.cpu_model is None
    assert "unavailable" in d.hardware.cpu_model_status


def test_repository_placeholder_handling() -> None:
    d = _decl()
    data = d.to_dict()
    # This repo's own game.toml declares real intended (not-yet-pushed)
    # GitHub URLs -- never a fabricated value, and round-trips cleanly.
    assert data["police_repository"] == PRIVATE.game.repos.get("police")
    assert data["thief_repository"] == PRIVATE.game.repos.get("thief")
    assert PeerDeclaration.from_dict(data).thief_repository == data["thief_repository"]


def test_unavailable_gpu_handling() -> None:
    hw = dataclasses.replace(_HW, gpu_model=None, gpu_available=False, vram_gb=None)
    d = _decl(hardware=hw)
    data = d.to_dict()
    assert data["hardware"]["gpu_model"] is None
    assert data["hardware"]["gpu_available"] is False
    assert data["hardware"]["vram_gb"] is None


def test_real_probe_never_fabricates_gpu() -> None:
    hw = probe_hardware()
    assert hw.gpu_model is None and hw.vram_gb is None
    assert hw.gpu_available is False
    assert hw.operating_system  # OS always known


def test_config_hash_mismatch_detected() -> None:
    d = _decl(config_sha256="a" * 64)
    problems = declaration_mismatches(
        d, expected_config_sha256="b" * 64, expected_group_id=PRIVATE.game.group_id
    )
    assert "shared_config_sha256 mismatch" in problems


def test_identity_mismatch_detected() -> None:
    d = _decl(config_sha256="a" * 64)
    problems = declaration_mismatches(
        d, expected_config_sha256="a" * 64, expected_group_id="some-other-group"
    )
    assert any("identity" in p for p in problems)


def test_schema_version_mismatch_detected_via_checks() -> None:
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


def test_secret_like_field_rejected() -> None:
    from thief_peer.services.artifacts import assert_no_credentials

    d = _decl()
    data = d.to_dict()
    data["thief_repository"] = "https://user:api_key=SECRETVALUE@example.invalid/thief"
    with pytest.raises(SchemaValidationError):
        assert_no_credentials(data)


def test_unknown_field_rejected() -> None:
    d = _decl()
    data = d.to_dict()
    data["totally_unrecognized_field"] = "sneaky"
    with pytest.raises(SchemaValidationError, match="unknown declaration field"):
        PeerDeclaration.from_dict(data)


def test_unknown_hardware_field_rejected() -> None:
    d = _decl()
    data = d.to_dict()
    data["hardware"]["unexpected_key"] = 1
    with pytest.raises(SchemaValidationError, match="unknown hardware field"):
        PeerDeclaration.from_dict(data)


def test_supported_legacy_alias_normalization() -> None:
    d = _decl()
    data = d.to_dict()
    data["commit_hash"] = data.pop("git_commit")
    data["config_sha256"] = data.pop("shared_config_sha256")
    reloaded = PeerDeclaration.from_dict(data)
    assert reloaded.git_commit == d.git_commit
    assert reloaded.shared_config_sha256 == d.shared_config_sha256
    assert "commit_hash" not in reloaded.to_dict()
    assert "config_sha256" not in reloaded.to_dict()


def test_ambiguous_alias_rejected() -> None:
    d = _decl()
    data = d.to_dict()
    data["commit_hash"] = "conflicting-value-not-matching-git_commit"
    with pytest.raises(SchemaValidationError, match="ambiguous"):
        PeerDeclaration.from_dict(data)


def test_no_credentials_in_serialized_declaration() -> None:
    blob = canonical_json_bytes(_decl().to_dict()).decode("utf-8").lower()
    for needle in ("secret", "password", "api_key", "token.json", "credentials.json"):
        assert needle not in blob, f"{needle!r} present in declaration"
    # 'token_budget' is a legitimate FIELD NAME, not a secret value.
    assert "token_budget" in blob
