"""Assemble a canonical PeerDeclaration from live, non-fabricated inputs
(session recovery step C). Split out of ``declaration.py`` to stay under
the 150-line cap.
"""

from __future__ import annotations

import subprocess
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from thief_peer.domain.declaration import SCHEMA_VERSION, PeerDeclaration, hardware_to_dict
from thief_peer.domain.hardware import HardwareInfo, probe_hardware
from thief_peer.shared.canonical_json import canonical_sha256_hex
from thief_peer.shared.private_config import PrivateGameConfig


def git_commit_hash(repo_root: Path) -> str:
    """The exact current commit of THIS repo via ``git rev-parse HEAD``.

    Never a fabricated hash; returns "unknown" if git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, check=False,
        )  # fmt: skip
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
class DeclarationContext:
    """The series-level + network inputs a caller supplies for one
    declaration; identity/strategy/banter fields are read directly from
    the supplied ``PrivateGameConfig`` instead of being repeated here."""

    role: str
    game_id: str
    game_uid: str
    token_budget: int
    num_sub_games: int
    config_sha256: str
    my_mcp_url: str
    opponent_mcp_url: str


def build_declaration(
    private: PrivateGameConfig,
    context: DeclarationContext,
    repo_root: Path,
    *,
    hardware: HardwareInfo | None = None,
    now: datetime | None = None,
) -> PeerDeclaration:
    """Build a declaration, probing hardware unless one was injected (for tests).

    ``content_sha256`` is computed over every OTHER field's canonical JSON --
    a documented commitment representation the replay verifier can
    recompute and compare, independent of this peer's own negotiation-time
    nonce-based Step-0 exchange.
    """
    hw = hardware if hardware is not None else probe_hardware()
    stamp = now or datetime.now(UTC)
    police_mcp_url = context.my_mcp_url if context.role == "police" else context.opponent_mcp_url
    thief_mcp_url = context.my_mcp_url if context.role == "thief" else context.opponent_mcp_url
    pre_hash_fields = {
        "schema_version": SCHEMA_VERSION,
        "game_id": context.game_id,
        "game_uid": context.game_uid,
        "role": context.role,
        "group_id": private.game.group_id,
        "group_name": private.game.group_name,
        "members": list(private.game.members),
        "police_repository": private.game.repos.get("police", "local-placeholder://police_peer"),
        "thief_repository": private.game.repos.get("thief", "local-placeholder://thief_peer"),
        "police_mcp_url": police_mcp_url,
        "thief_mcp_url": thief_mcp_url,
        "timezone": str(stamp.astimezone().tzinfo),
        "timestamp": stamp.isoformat(),
        "token_budget": context.token_budget,
        "num_sub_games": context.num_sub_games,
        "shared_config_sha256": context.config_sha256,
        "code_version": code_version(repo_root),
        "git_commit": git_commit_hash(repo_root),
        "strategy_class": private.strategy.thief_class,
        "banter_provider": private.trash_talk.provider,
        "hardware": hardware_to_dict(hw),
    }
    return PeerDeclaration(
        content_sha256=canonical_sha256_hex(pre_hash_fields),
        members=tuple(private.game.members),
        hardware=hw,
        **{k: v for k, v in pre_hash_fields.items() if k not in ("members", "hardware")},
    )
