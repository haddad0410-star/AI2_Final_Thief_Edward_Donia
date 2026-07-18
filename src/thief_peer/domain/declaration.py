"""Step-0 peer declaration (Batch 2 Phase 5, book Ch.5.5).

Assembles the identity + provenance + hardware record that both peers seal and
exchange before the first move, so a stronger machine or a different code version
cannot be substituted mid-series undetected. This module does NOT own game-id
derivation (the caller fills ``game_id``/``game_uid``); it never fabricates
hardware values (see :mod:`thief_peer.domain.hardware`) and carries no secrets.
"""

from __future__ import annotations

import subprocess
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from thief_peer.domain.hardware import HardwareInfo, probe_hardware
from thief_peer.shared.private_config import PrivateGameConfig


def git_commit_hash(repo_root: Path) -> str:
    """The exact current commit of THIS repo via ``git rev-parse HEAD``.

    Actually runs the subprocess against ``repo_root``; returns "unknown" (never
    a fabricated hash) if git is unavailable or the directory is not a repo."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def code_version(repo_root: Path) -> str:
    """Read ``[project].version`` from this repo's pyproject.toml."""
    try:
        data = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
        return str(data.get("project", {}).get("version", "0.0.0"))
    except (OSError, tomllib.TOMLDecodeError):
        return "0.0.0"


@dataclass(frozen=True, slots=True)
class PeerDeclaration:
    """The full Step-0 declaration for one peer (whole series)."""

    schema_version: str
    game_id: str
    game_uid: str
    role: str
    group_name: str
    group_id: str
    members: tuple[str, ...]
    repository: str
    code_version: str
    commit_hash: str
    strategy_class: str
    banter_provider: str
    token_budget: int
    timezone: str
    timestamp: str
    config_sha256: str
    hardware: HardwareInfo = field(default_factory=probe_hardware)

    def to_canonical_dict(self) -> dict:
        """A JSON-serializable dict (for canonicalization + sealing)."""
        data = asdict(self)
        data["members"] = list(self.members)
        return data


def declaration_mismatches(
    declaration: PeerDeclaration,
    *,
    expected_config_sha256: str,
    expected_group_id: str,
    expected_schema_version: str = "declaration/1",
) -> tuple[str, ...]:
    """Return a tuple of human-readable mismatch reasons (empty == compatible).

    Detects the three refuse-to-play conditions: a config-hash mismatch (the two
    peers do not hold byte-identical terms), an identity mismatch, and a schema
    version mismatch."""
    problems: list[str] = []
    if declaration.config_sha256 != expected_config_sha256:
        problems.append("config_sha256 mismatch")
    if declaration.group_id != expected_group_id:
        problems.append("identity (group_id) mismatch")
    if declaration.schema_version != expected_schema_version:
        problems.append("schema version mismatch")
    return tuple(problems)


def build_declaration(
    private: PrivateGameConfig,
    token_budget: int,
    config_sha256: str,
    repo_root: Path,
    *,
    game_id: str = "",
    game_uid: str = "",
    hardware: HardwareInfo | None = None,
    now: datetime | None = None,
) -> PeerDeclaration:
    """Assemble a thief PeerDeclaration from private config + live provenance.

    ``game_id``/``game_uid`` are placeholders the caller fills after id
    derivation. Hardware is probed live unless injected (tests inject it)."""
    stamp = now or datetime.now(UTC)
    return PeerDeclaration(
        schema_version="declaration/1",
        game_id=game_id,
        game_uid=game_uid,
        role="thief",
        group_name=private.game.group_name,
        group_id=private.game.group_id,
        members=tuple(private.game.members),
        repository=private.game.repos.get("thief", "local-placeholder://thief_peer"),
        code_version=code_version(repo_root),
        commit_hash=git_commit_hash(repo_root),
        strategy_class=private.strategy.thief_class,
        banter_provider=private.trash_talk.provider,
        token_budget=token_budget,
        timezone=str(stamp.tzinfo),
        timestamp=stamp.isoformat(),
        config_sha256=config_sha256,
        hardware=hardware if hardware is not None else probe_hardware(),
    )
