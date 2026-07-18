"""Canonical commit/reveal sealing and mutual audit (Batch 2 Phase 4).

Design decision -- NO hash chain across steps (see docs/adr/ADR-0014): the
protocol contract does not mandate one, and each step's commitment is
independently verifiable. Record ordering/gaps are validated separately
(sequence checks in Phase 6/12), which keeps the wire format interoperable with
an independently-built Police peer.
"""

from __future__ import annotations

from thief_peer.domain.sealing.audit import (
    AuditOutcome,
    AuditReport,
    audit_sealed_records,
    steps_in_order,
    verify_hash,
)
from thief_peer.domain.sealing.commit import SealedRecord, commit_hash, new_nonce, seal
from thief_peer.domain.sealing.exchange import CommitRevealExchange, ExchangeError, Phase
from thief_peer.domain.sealing.payload import CURRENT_SCHEMA_VERSION, SealedTurnPayload

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "AuditOutcome",
    "AuditReport",
    "CommitRevealExchange",
    "ExchangeError",
    "Phase",
    "SealedRecord",
    "SealedTurnPayload",
    "audit_sealed_records",
    "commit_hash",
    "new_nonce",
    "seal",
    "steps_in_order",
    "verify_hash",
]
