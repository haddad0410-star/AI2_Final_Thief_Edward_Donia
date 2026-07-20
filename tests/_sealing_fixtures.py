"""Shared test-only builders for sealed-record tests.

The FIXED_NONCE here is a deterministic, non-secret value used ONLY to make test
vectors reproducible. Production code always calls the real CSPRNG
(``sealing.new_nonce``); this constant must never appear in production paths.
"""

from __future__ import annotations

import dataclasses

from thief_peer.domain.sealing import SealedRecord, SealedTurnPayload, seal

FIXED_NONCE = "test-only-fixed-nonce-not-for-production-0000000000000000"  # noqa: S105


def make_payload(step: int = 0, nonce: str | None = None, **overrides: object) -> SealedTurnPayload:
    """Build a valid thief sealed payload with sensible defaults for tests."""
    base = {
        "step": step,
        "role": "thief",
        "sub_game_number": 1,
        "state": f"pos=3,{3 + step}",
        "move": "E",
        "intent": "truth",
        "hint": "The northern avenues feel exposed right now.",
        "scent_digest": "deadbeef" * 8,
        "scent_grid": ((0.0, 0.0), (0.0, 0.0)),
        "timestamp": "2026-07-18T00:00:00+00:00",
        "nonce": nonce if nonce is not None else f"{FIXED_NONCE}-{step}",
        "config_sha256": "a" * 64,
        "win_claim": False,
    }
    base.update(overrides)
    return SealedTurnPayload(**base)  # type: ignore[arg-type]


def make_record(step: int = 0, **overrides: object) -> SealedRecord:
    return seal(make_payload(step, **overrides))


def tamper(record: SealedRecord, **field_overrides: object) -> SealedRecord:
    """Return a record whose PAYLOAD is mutated but whose published commit_hash
    is kept from the original -- i.e. a forged reveal that must fail the audit."""
    forged_payload = dataclasses.replace(record.payload, **field_overrides)
    return SealedRecord(payload=forged_payload, commit_hash=record.commit_hash)
