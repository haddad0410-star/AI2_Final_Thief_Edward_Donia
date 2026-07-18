"""Phase 4 tamper injection: mutate each sealed field one at a time and confirm
the recomputation audit detects every single mutation (tamper_forfeit).

The saved evidence file integration_lab/evidence/tamper_tests/... is the real
pytest output of this module."""

from __future__ import annotations

import pytest
from _sealing_fixtures import make_record, tamper

from thief_peer.domain.sealing import AuditOutcome, audit_sealed_records, steps_in_order

# Each case mutates exactly ONE field of an otherwise-valid revealed record.
TAMPER_CASES = [
    ("move", {"move": "W"}),
    ("hint", {"hint": "a different lie entirely"}),
    ("intent_verdict", {"intent": "lie"}),
    ("scent_data", {"scent_digest": "f00dface" * 8}),
    ("barrier_location", {"barrier_placed": (5, 5)}),
    ("capture_claim", {"capture_claim": (2, 2)}),
    ("step_number", {"step": 99}),
    ("role", {"role": "police"}),
    ("timestamp", {"timestamp": "2099-01-01T00:00:00+00:00"}),
    ("nonce", {"nonce": "forged-nonce-value"}),
    ("config_hash", {"config_sha256": "b" * 64}),
    ("claim_response", {"claim_response": True}),
    ("win_claim", {"win_claim": True}),
]


@pytest.mark.parametrize("label,mutation", TAMPER_CASES, ids=[c[0] for c in TAMPER_CASES])
def test_single_field_mutation_is_detected(label: str, mutation: dict) -> None:
    original = make_record(step=0)
    forged = tamper(original, **mutation)
    report = audit_sealed_records([forged])
    assert report.outcome is AuditOutcome.TAMPER_FORFEIT, f"{label} mutation went undetected"
    # A mismatch is recorded (the reported step is the forged payload's step,
    # which for the step_number case is itself the mutated value).
    assert report.mismatched_steps, f"{label} mutation produced no mismatch record"


def test_untampered_records_verify() -> None:
    records = [make_record(step=i) for i in range(5)]
    report = audit_sealed_records(records)
    assert report.outcome is AuditOutcome.VERIFIED


def test_record_order_tamper_is_detected_by_sequence_check() -> None:
    records = [make_record(step=i) for i in range(4)]
    # Per-record hashes still match after a reorder, but the step sequence check
    # catches the reordering that hashing alone cannot.
    reordered = [records[0], records[2], records[1], records[3]]
    assert audit_sealed_records(reordered).outcome is AuditOutcome.VERIFIED
    assert steps_in_order(records) is True
    assert steps_in_order(reordered) is False


def test_missing_record_gap_is_detected_by_sequence_check() -> None:
    records = [make_record(step=i) for i in (0, 1, 3)]  # step 2 dropped
    assert steps_in_order(records) is False
