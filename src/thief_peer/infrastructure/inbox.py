"""BoundedInbox: a capacity-capped, duplicate-aware message queue (Phase 6).

Tool handlers enqueue validated messages here and return immediately; the local
runtime drains it. The queue is bounded -- once full it rejects (backpressure)
rather than growing without limit, defending against a flooding opponent. Both a
correlation-id conflict check and a logical-key idempotency check are provided,
extending the Batch 1 ``record_or_check_conflict`` pattern.
"""

from __future__ import annotations

import queue
from dataclasses import dataclass


class InboxFullError(Exception):
    """Raised when the bounded inbox has reached capacity."""


@dataclass(frozen=True, slots=True)
class InboxItem:
    """One validated message plus the logical key it was accepted under."""

    logical_key: str
    message: dict


class BoundedInbox:
    """A thread-safe, size-capped inbox with duplicate detection."""

    def __init__(self, capacity: int = 100) -> None:
        self._queue: queue.Queue[InboxItem] = queue.Queue(maxsize=capacity)
        self._seen_by_correlation: dict[str, dict] = {}
        self._seen_by_key: dict[str, dict] = {}

    @property
    def capacity(self) -> int:
        return self._queue.maxsize

    def size(self) -> int:
        return self._queue.qsize()

    def is_duplicate_conflict(self, key: str, message: dict) -> bool:
        """True iff `key` was already seen with a DIFFERENT payload (a conflict).
        An identical repeat returns False (it is an idempotent replay)."""
        previous = self._seen_by_key.get(key)
        return previous is not None and previous != message

    def is_idempotent_replay(self, key: str, message: dict) -> bool:
        """True iff `key` was already seen with the identical payload."""
        return self._seen_by_key.get(key) == message

    def correlation_conflict(self, correlation_id: str, message: dict) -> bool:
        """True iff this correlation_id was seen with a different payload."""
        previous = self._seen_by_correlation.get(correlation_id)
        return previous is not None and previous != message

    def enqueue(self, key: str, message: dict, correlation_id: str = "") -> None:
        """Record and enqueue a validated message. Raises :class:`InboxFullError`
        if the bounded queue is at capacity (the caller returns backpressure)."""
        try:
            self._queue.put_nowait(InboxItem(logical_key=key, message=message))
        except queue.Full as exc:
            raise InboxFullError(f"inbox at capacity ({self.capacity})") from exc
        self._seen_by_key[key] = message
        if correlation_id:
            self._seen_by_correlation[correlation_id] = message

    def drain(self) -> list[InboxItem]:
        """Remove and return all currently-queued items (runtime side)."""
        items: list[InboxItem] = []
        while not self._queue.empty():
            items.append(self._queue.get_nowait())
        return items

    def pop_matching(self, predicate) -> dict | None:
        """Remove and return the first currently-queued message satisfying
        ``predicate(message)``, re-enqueuing every other item in its original
        order. Returns ``None`` if nothing currently queued matches (the
        caller is expected to poll again after a short delay -- this never
        blocks)."""
        match: dict | None = None
        for item in self.drain():
            if match is None and predicate(item.message):
                match = item.message
                continue
            self._queue.put_nowait(item)
        return match
