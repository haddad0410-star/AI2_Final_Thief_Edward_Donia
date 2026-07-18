"""Watchdog: local runtime health / stall detection (Batch 2 Phase 3).

Monitors *this* peer's own progress against a monotonic deadline. On a detected
stall it asks for graceful shutdown first, then escalates; it records the reason
and bounds the number of escalations so it can never spin in an infinite
restart loop. A dead local subprocess (where one exists) is reported via
:meth:`note_subprocess_dead`. Terminal exhaustion yields an explicit
technical-loss outcome rather than a hang.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from thief_peer.domain.captures import SubGameResult


class WatchdogStatus(StrEnum):
    """The verdict of a single :meth:`Watchdog.check`."""

    HEALTHY = "healthy"
    GRACEFUL_SHUTDOWN = "graceful_shutdown"  # first response to a stall
    ESCALATED = "escalated"  # forced stop after graceful attempt(s)
    TECHNICAL_LOSS = "technical_loss"  # retries exhausted / subprocess dead


@dataclass(frozen=True, slots=True)
class WatchdogOutcome:
    """The result of a check, carrying the reason for any escalation."""

    status: WatchdogStatus
    reason: str
    escalations: int

    @property
    def is_technical_loss(self) -> bool:
        return self.status is WatchdogStatus.TECHNICAL_LOSS

    def sub_game_result(self) -> SubGameResult | None:
        """The SubGameResult this outcome forces, if any."""
        return SubGameResult.TECHNICAL_LOSS if self.is_technical_loss else None


class Watchdog:
    """Bounded stall detector. `max_retries` caps escalations before a
    technical loss is declared -- guaranteeing termination."""

    def __init__(
        self,
        timeout_seconds: float,
        max_retries: int = 3,
        now_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._timeout = float(timeout_seconds)
        self._max_retries = max(0, max_retries)
        self._now_fn = now_fn
        self._last_progress = now_fn()
        self._escalations = 0
        self._dead = False

    def note_progress(self) -> None:
        """Record that forward progress happened (resets the stall timer)."""
        self._last_progress = self._now_fn()

    def note_subprocess_dead(self, reason: str = "local subprocess exited") -> None:
        """Mark a monitored local subprocess as dead -- next check is fatal."""
        self._dead = True
        self._dead_reason = reason

    def stalled(self) -> bool:
        """True once no progress has been noted within the timeout window."""
        return (self._now_fn() - self._last_progress) > self._timeout

    @property
    def escalations(self) -> int:
        return self._escalations

    def check(self) -> WatchdogOutcome:
        """Evaluate health once and advance the escalation ladder if stalled."""
        if self._dead:
            return WatchdogOutcome(
                WatchdogStatus.TECHNICAL_LOSS,
                getattr(self, "_dead_reason", "dead"),
                self._escalations,
            )
        if not self.stalled():
            return WatchdogOutcome(WatchdogStatus.HEALTHY, "", self._escalations)

        self._escalations += 1
        if self._escalations > self._max_retries:
            return WatchdogOutcome(
                WatchdogStatus.TECHNICAL_LOSS,
                f"stall persisted past {self._max_retries} retries",
                self._escalations,
            )
        if self._escalations == 1:
            return WatchdogOutcome(
                WatchdogStatus.GRACEFUL_SHUTDOWN, "stall detected; requesting graceful stop", 1
            )
        return WatchdogOutcome(
            WatchdogStatus.ESCALATED, "graceful stop did not clear the stall", self._escalations
        )
