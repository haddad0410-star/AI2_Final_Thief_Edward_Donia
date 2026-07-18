"""Final audit: constant-time recomputation of every commitment (Phase 4).

At the end of a sub-game both peers reveal all nonces; each recomputes every
``H_commit`` and compares it, in constant time, to the value published at commit
time. Any mismatch is a ``tamper_forfeit`` -- a hard technical loss with no
partial credit (book Ch.5.4). Nonce reuse across steps is also disqualifying.

``secrets.compare_digest`` is called via the module attribute (not a bound
import) so a test can patch ``secrets.compare_digest`` and assert it was used.
"""

from __future__ import annotations

import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from thief_peer.domain.sealing.commit import SealedRecord, commit_hash
from thief_peer.shared.canonical_json import canonical_sha256_hex


class AuditOutcome(StrEnum):
    """The verdict of a completed audit."""

    VERIFIED = "verified"
    TAMPER_FORFEIT = "tamper_forfeit"


@dataclass(frozen=True, slots=True)
class AuditReport:
    """The structured result of auditing a list of sealed records."""

    outcome: AuditOutcome
    mismatched_steps: tuple[int, ...]
    reused_nonces: tuple[str, ...]
    reason: str

    @property
    def verified(self) -> bool:
        return self.outcome is AuditOutcome.VERIFIED


def verify_hash(payload_dict: dict, expected_hash: str) -> bool:
    """Constant-time check that ``payload_dict`` hashes to ``expected_hash``."""
    actual = canonical_sha256_hex(payload_dict)
    return secrets.compare_digest(actual, expected_hash)


def steps_in_order(records: Sequence[SealedRecord], start: int = 0) -> bool:
    """True iff the records' step numbers are contiguous and ascending from
    ``start`` -- detects reordering, gaps, and duplicate steps (the "record
    order" tamper case, which per-record hashing alone cannot catch)."""
    steps = [record.payload.step for record in records]
    return steps == list(range(start, start + len(steps)))


def audit_sealed_records(records: Sequence[SealedRecord]) -> AuditReport:
    """Recompute and constant-time-compare every commitment; detect nonce reuse.

    Returns VERIFIED only when every record's payload still hashes to its
    published commit hash AND no nonce is repeated. Otherwise TAMPER_FORFEIT.
    """
    mismatched: list[int] = []
    for record in records:
        recomputed = commit_hash(record.payload)
        if not secrets.compare_digest(recomputed, record.commit_hash):
            mismatched.append(record.payload.step)

    seen: set[str] = set()
    reused: list[str] = []
    for record in records:
        nonce = record.payload.nonce
        if nonce in seen:
            reused.append(nonce)
        seen.add(nonce)

    if mismatched or reused:
        reasons = []
        if mismatched:
            reasons.append(f"hash mismatch at steps {sorted(set(mismatched))}")
        if reused:
            reasons.append(f"{len(reused)} reused nonce(s)")
        return AuditReport(
            outcome=AuditOutcome.TAMPER_FORFEIT,
            mismatched_steps=tuple(sorted(set(mismatched))),
            reused_nonces=tuple(reused),
            reason="; ".join(reasons),
        )
    return AuditReport(
        outcome=AuditOutcome.VERIFIED,
        mismatched_steps=(),
        reused_nonces=(),
        reason="all commitments recomputed and matched",
    )
