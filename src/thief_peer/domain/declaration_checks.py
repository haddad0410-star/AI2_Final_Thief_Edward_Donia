"""Cross-check an incoming declaration against locally-expected values
(session recovery step C). Split out of ``declaration.py`` to stay under
the 150-line cap.
"""

from __future__ import annotations

from thief_peer.domain.declaration import SCHEMA_VERSION, PeerDeclaration


def declaration_mismatches(
    declaration: PeerDeclaration,
    *,
    expected_config_sha256: str,
    expected_group_id: str,
    expected_schema_version: str = SCHEMA_VERSION,
) -> tuple[str, ...]:
    """Return a tuple of human-readable mismatch reasons (empty == compatible).

    Detects the three refuse-to-play conditions: a config-hash mismatch (the two
    peers do not hold byte-identical terms), an identity mismatch, and a schema
    version mismatch."""
    problems: list[str] = []
    if declaration.shared_config_sha256 != expected_config_sha256:
        problems.append("shared_config_sha256 mismatch")
    if declaration.group_id != expected_group_id:
        problems.append("identity (group_id) mismatch")
    if declaration.schema_version != expected_schema_version:
        problems.append("schema version mismatch")
    return tuple(problems)
