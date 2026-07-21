"""Batch 3.6 Task 4: end-to-end hint-verdict visibility proof -- the intent
verdict must be absent at the live reveal but present and verifiable at
the final audit.
"""

from __future__ import annotations

import dataclasses

from thief_peer.domain.sealing import SealedTurnPayload, commit_hash, seal
from thief_peer.shared.canonical_json import canonical_sha256_hex


def _payload(intent: str = "lie") -> SealedTurnPayload:
    grid = tuple(tuple(0.0 for _ in range(7)) for _ in range(7))
    return SealedTurnPayload(
        step=0,
        role="thief",
        sub_game_number=1,
        state="pos=0,0;visited=1",
        move="N",
        intent=intent,
        hint="the eastern quarter looks promising",
        scent_digest=canonical_sha256_hex([list(row) for row in grid]),
        scent_grid=grid,
        timestamp="2026-07-18T00:00:00+00:00",
        nonce="e" * 64,
        config_sha256="f" * 64,
    )


def test_live_reveal_omits_intent_but_final_audit_reveals_it() -> None:
    payload = _payload(intent="lie")
    record = seal(payload)
    live_reveal = payload.public_reveal_dict()
    assert "intent" not in live_reveal
    assert live_reveal["hint"] == "the eastern quarter looks promising"

    # final audit: the LOCALLY-held record (never transmitted at reveal
    # time) still carries the full payload, including intent.
    assert record.payload.intent == "lie"
    assert record.recompute_matches() is True


def test_final_audit_detects_a_forged_intent() -> None:
    honest = _payload(intent="lie")
    committed_hash = commit_hash(honest)
    forged = dataclasses.replace(honest, intent="truth")
    assert commit_hash(forged) != committed_hash


def test_live_reveal_never_contains_nonce_or_intent_together() -> None:
    for intent in ("truth", "lie"):
        payload = _payload(intent=intent)
        revealed = payload.public_reveal_dict()
        assert "nonce" not in revealed
        assert "intent" not in revealed
