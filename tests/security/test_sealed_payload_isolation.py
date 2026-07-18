"""Phase 4: the sealed payload can never hold the opponent's true position.

A field-name introspection guard (mirrors tests/unit/test_local_peer_state.py)
plus a serialized-content scan for credential-like substrings."""

from __future__ import annotations

import dataclasses

from _sealing_fixtures import make_payload

from thief_peer.domain.sealing import SealedTurnPayload
from thief_peer.shared.canonical_json import canonical_json_bytes

FORBIDDEN_FIELD_SUBSTRINGS = (
    "opponent_position",
    "opponent_true",
    "true_position",
    "enemy_position",
    "police_position",
)


def test_sealed_payload_has_no_opponent_position_field() -> None:
    names = {f.name for f in dataclasses.fields(SealedTurnPayload)}
    for forbidden in FORBIDDEN_FIELD_SUBSTRINGS:
        assert not any(forbidden in name for name in names), names


def test_serialized_payload_has_no_credentials() -> None:
    blob = canonical_json_bytes(make_payload(step=0).to_canonical_dict()).decode("utf-8").lower()
    for needle in ("secret", "password", "api_key", "token.json", "credentials"):
        assert needle not in blob, f"{needle!r} unexpectedly present in sealed payload"
