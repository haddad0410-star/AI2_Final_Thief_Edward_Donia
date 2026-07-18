"""CommitRevealExchange: enforces the Commit -> Acknowledge -> Reveal order
for one sub-game's steps (Batch 2 Phase 4, book Fig.6 sequence).

This is the record-level guard (distinct from the lifecycle state machine): it
rejects a reveal that arrives before its acknowledgment, a duplicate reveal, and
-- at audit -- any step that was committed but never revealed (incomplete
reveal). A reveal whose payload does not hash to the committed value is rejected
immediately, before the final audit even runs.
"""

from __future__ import annotations

from enum import StrEnum

from thief_peer.domain.sealing.commit import SealedRecord, commit_hash


class ExchangeError(Exception):
    """Raised on an out-of-order, duplicate, or mismatched exchange step."""


class Phase(StrEnum):
    COMMITTED = "committed"
    ACKNOWLEDGED = "acknowledged"
    REVEALED = "revealed"


class CommitRevealExchange:
    """Per-step phase tracker for one sub-game's commit/reveal exchange."""

    def __init__(self) -> None:
        self._phase: dict[int, Phase] = {}
        self._committed_hash: dict[int, str] = {}
        self._records: dict[int, SealedRecord] = {}

    def commit(self, step: int, published_hash: str) -> None:
        """Register a commitment for `step`. A second, conflicting commit for an
        already-committed step is a rewrite-history violation."""
        if step in self._committed_hash:
            if self._committed_hash[step] != published_hash:
                raise ExchangeError(f"conflicting re-commit for step {step}")
            return  # idempotent identical re-commit
        self._committed_hash[step] = published_hash
        self._phase[step] = Phase.COMMITTED

    def acknowledge(self, step: int) -> None:
        """Acknowledge a committed step. Cannot ack an uncommitted step."""
        if self._phase.get(step) is not Phase.COMMITTED:
            raise ExchangeError(f"cannot acknowledge step {step} in phase {self._phase.get(step)}")
        self._phase[step] = Phase.ACKNOWLEDGED

    def reveal(self, step: int, record: SealedRecord) -> None:
        """Reveal a step's record. Requires a prior acknowledgment, rejects
        duplicates, and verifies the payload matches the committed hash."""
        phase = self._phase.get(step)
        if phase is None or phase is Phase.COMMITTED:
            raise ExchangeError(f"reveal before acknowledgment for step {step}")
        if phase is Phase.REVEALED:
            raise ExchangeError(f"duplicate reveal for step {step}")
        if commit_hash(record.payload) != self._committed_hash[step]:
            raise ExchangeError(f"revealed payload does not match commitment at step {step}")
        self._phase[step] = Phase.REVEALED
        self._records[step] = record

    def revealed_records(self) -> tuple[SealedRecord, ...]:
        """All revealed records, ordered by step."""
        return tuple(self._records[s] for s in sorted(self._records))

    def incomplete_steps(self) -> tuple[int, ...]:
        """Steps that were committed/acknowledged but never revealed."""
        return tuple(sorted(s for s, p in self._phase.items() if p is not Phase.REVEALED))
