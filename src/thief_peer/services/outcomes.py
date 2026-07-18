"""Typed sub-game outcomes for the runtime (Batch 2 Phase 9/10).

Every way a sub-game can end -- capture, survival, or a technical loss (opponent
malformed, deadline exceeded, watchdog escalation) -- is an explicit value, never
a hang.
"""

from __future__ import annotations

from dataclasses import dataclass

from thief_peer.domain.captures import SubGameResult
from thief_peer.domain.sealing import AuditReport, SealedRecord


@dataclass(frozen=True, slots=True)
class TurnResult:
    """The result of running one turn."""

    ended: bool
    outcome: SubGameResult | None
    reason: str


@dataclass(frozen=True, slots=True)
class SubGameRunResult:
    """The result of running one full sub-game."""

    result: SubGameResult
    steps_taken: int
    reason: str
    records: tuple[SealedRecord, ...] = ()
    audit: AuditReport | None = None
    police_score: int = 0
    thief_score: int = 0

    @property
    def technical_loss(self) -> bool:
        return self.result is SubGameResult.TECHNICAL_LOSS
