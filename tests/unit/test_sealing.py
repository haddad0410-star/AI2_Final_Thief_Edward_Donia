"""Phase 4: commit/reveal sealing mechanics -- nonces, canonical hashing,
Unicode, constant-time compare, and the commit->ack->reveal exchange."""

from __future__ import annotations

import secrets

from _sealing_fixtures import make_payload, make_record

from thief_peer.domain.sealing import (
    AuditOutcome,
    CommitRevealExchange,
    ExchangeError,
    audit_sealed_records,
    commit_hash,
    new_nonce,
    seal,
)
from thief_peer.shared.canonical_json import canonical_sha256_hex


def test_new_nonce_is_fresh_and_long() -> None:
    nonces = {new_nonce() for _ in range(1000)}
    assert len(nonces) == 1000  # no collisions
    assert all(len(n) == 64 for n in nonces)  # 32 bytes -> 64 hex chars


def test_commit_hash_is_canonical_and_stable() -> None:
    payload = make_payload(step=2)
    assert commit_hash(payload) == canonical_sha256_hex(payload.to_canonical_dict())
    assert commit_hash(payload) == commit_hash(payload)  # deterministic


def test_canonical_ordering_independent_of_dict_insertion() -> None:
    payload = make_payload(step=1)
    d = payload.to_canonical_dict()
    reordered = dict(reversed(list(d.items())))
    assert canonical_sha256_hex(d) == canonical_sha256_hex(reordered)


def test_hebrew_hint_round_trips_in_canonical_hash() -> None:
    payload = make_payload(hint="הגנב פונה מזרחה אל הרחוב הצפוני")
    # A Hebrew hint hashes stably and matches a fresh recomputation.
    assert commit_hash(payload) == commit_hash(make_payload(hint="הגנב פונה מזרחה אל הרחוב הצפוני"))
    assert seal(payload).recompute_matches() is True


def test_valid_complete_audit_succeeds() -> None:
    records = [make_record(step=i) for i in range(4)]
    report = audit_sealed_records(records)
    assert report.outcome is AuditOutcome.VERIFIED
    assert report.verified is True


def test_nonce_reuse_is_detected() -> None:
    r0 = make_record(step=0, nonce="same-nonce-value")
    r1 = make_record(step=1, nonce="same-nonce-value")
    report = audit_sealed_records([r0, r1])
    assert report.outcome is AuditOutcome.TAMPER_FORFEIT
    assert report.reused_nonces == ("same-nonce-value",)


def test_constant_time_compare_is_actually_used(monkeypatch) -> None:
    calls: list[tuple] = []
    real = secrets.compare_digest

    def spy(a, b):
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr(secrets, "compare_digest", spy)
    audit_sealed_records([make_record(step=0)])
    assert calls, "audit must verify via secrets.compare_digest"


def test_exchange_reveal_before_ack_is_rejected() -> None:
    record = make_record(step=0)
    ex = CommitRevealExchange()
    ex.commit(0, record.commit_hash)
    try:
        ex.reveal(0, record)  # no acknowledge() yet
        raise AssertionError("expected ExchangeError")
    except ExchangeError as exc:
        assert "before acknowledgment" in str(exc)


def test_exchange_duplicate_reveal_is_rejected() -> None:
    record = make_record(step=0)
    ex = CommitRevealExchange()
    ex.commit(0, record.commit_hash)
    ex.acknowledge(0)
    ex.reveal(0, record)
    try:
        ex.reveal(0, record)
        raise AssertionError("expected ExchangeError")
    except ExchangeError as exc:
        assert "duplicate reveal" in str(exc)


def test_exchange_incomplete_reveal_is_detected() -> None:
    ex = CommitRevealExchange()
    ex.commit(0, make_record(step=0).commit_hash)
    ex.acknowledge(0)  # committed + acked but never revealed
    assert ex.incomplete_steps() == (0,)


def test_exchange_conflicting_recommit_rejected() -> None:
    ex = CommitRevealExchange()
    ex.commit(0, "a" * 64)
    try:
        ex.commit(0, "b" * 64)
        raise AssertionError("expected ExchangeError")
    except ExchangeError as exc:
        assert "conflicting" in str(exc)
