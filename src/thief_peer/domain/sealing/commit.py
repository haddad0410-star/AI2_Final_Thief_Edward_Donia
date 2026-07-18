"""Commitment primitives: CSPRNG nonces and SHA-256 sealing (Phase 4).

Nonces come from :func:`secrets.token_hex` (a CSPRNG) -- never ``random``,
``hash()``, ``repr()``, ``pickle``, or a timestamp. The commitment hash is
``SHA256(canonical_json(payload))`` using the project's shared canonical encoder
(sorted keys, ``(",", ":")`` separators, UTF-8), so it round-trips Unicode
(including Hebrew) exactly. The nonce is part of the sealed payload but is never
transmitted until the final audit.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from thief_peer.domain.sealing.payload import SealedTurnPayload
from thief_peer.shared.canonical_json import canonical_sha256_hex

NONCE_BYTES = 32  # 256 bits of CSPRNG entropy -> 64 hex chars


def new_nonce() -> str:
    """A fresh, cryptographically-random hex nonce. Never reuse across steps."""
    return secrets.token_hex(NONCE_BYTES)


def commit_hash(payload: SealedTurnPayload) -> str:
    """``H_commit`` for a payload: SHA-256 of its canonical JSON encoding."""
    return canonical_sha256_hex(payload.to_canonical_dict())


@dataclass(frozen=True, slots=True)
class SealedRecord:
    """A committed step: the payload (held privately, nonce included) plus the
    ``H_commit`` that was published at commit time."""

    payload: SealedTurnPayload
    commit_hash: str

    def recompute_matches(self) -> bool:
        """True iff the payload still hashes to the published commit hash.
        Uses a constant-time compare via :mod:`secrets` in the audit layer."""
        return commit_hash(self.payload) == self.commit_hash


def seal(payload: SealedTurnPayload) -> SealedRecord:
    """Seal a payload, publishing only its hash. The returned record keeps the
    payload (with nonce) locally until the audit reveals it."""
    return SealedRecord(payload=payload, commit_hash=commit_hash(payload))
