"""DeadlineTracker: monotonic-clock time budgeting (Batch 2 Phase 3).

Uses ``time.monotonic`` by default -- never wall-clock -- so it is immune to
system-clock adjustments. Tests inject a fake ``now_fn`` (any zero-arg callable
returning seconds) and never sleep for real. ``remaining()`` is clamped at 0 so a
blown deadline never yields a negative budget.
"""

from __future__ import annotations

import time
from collections.abc import Callable


class DeadlineTracker:
    """A single time budget: start it, then query how much is left."""

    def __init__(
        self, timeout_seconds: float, now_fn: Callable[[], float] = time.monotonic
    ) -> None:
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must be >= 0")
        self._timeout = float(timeout_seconds)
        self._now_fn = now_fn
        self._start: float | None = None

    def start(self) -> DeadlineTracker:
        """Record the start instant (idempotent-safe: restarts the budget)."""
        self._start = self._now_fn()
        return self

    def _started_at(self) -> float:
        if self._start is None:
            self._start = self._now_fn()
        return self._start

    def elapsed(self) -> float:
        """Seconds since :meth:`start` (auto-starts on first query)."""
        return max(0.0, self._now_fn() - self._started_at())

    def remaining(self) -> float:
        """Seconds left before the deadline, never negative (clamped at 0)."""
        return max(0.0, self._timeout - self.elapsed())

    def expired(self) -> bool:
        """True once no budget remains."""
        return self.remaining() <= 0.0

    @property
    def timeout_seconds(self) -> float:
        """The total budget this tracker was created with."""
        return self._timeout

    def child(self, budget_seconds: float) -> DeadlineTracker:
        """Allocate a phase/child deadline capped by this tracker's remaining
        budget, sharing the same clock and started immediately. A child can never
        outlive its parent."""
        capped = min(float(budget_seconds), self.remaining())
        return DeadlineTracker(capped, now_fn=self._now_fn).start()
