"""SequenceTracker: per-sub-game turn ordering guard (Batch 2 Phase 6).

Enforces that the core commit-reveal phases arrive in order (commitment ->
reveal) and that steps advance by exactly one, so a stale step, a skipped
step, and an out-of-order reveal are all rejected. It is only ever fed
genuinely-new messages (the router filters idempotent replays first), so
accepting a message advances the tracker's state.

Per ``protocol_contract.md`` section 3.3, book Fig.6's "Acknowledge" step is
the synchronous FastMCP tool-call response to the commitment delivery itself
(both this repo's and the Police repo's real turn loops treat it that way --
neither ever sends a separate, discriminated ``commit_ack`` message type), so
no third core phase is tracked here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_CORE_PHASE_INDEX = {"commitment": 0, "reveal": 1}
#: ``commit_ack`` remains a structurally-valid message type (turn_message.py)
#: for a sender that chooses to emit it, but is optional/informational here --
#: never required before a reveal is accepted (see module docstring).
_AUX_TYPES = frozenset(
    {"hint", "scent", "barrier", "capture_claim", "capture_response", "commit_ack"}
)


@dataclass
class _SubGameCursor:
    step: int = 0
    phase: int = -1  # highest core-phase index reached in the current step


@dataclass
class SequenceTracker:
    """Tracks the active step and phase for each sub-game."""

    _cursors: dict[int, _SubGameCursor] = field(default_factory=dict)

    def _cursor(self, sub_game: int) -> _SubGameCursor:
        return self._cursors.setdefault(sub_game, _SubGameCursor())

    def check_and_advance(self, sub_game: int, step: int, message_type: str) -> tuple[bool, str]:
        """Validate a new message against the ordering rules, advancing on accept.
        Returns ``(accepted, reason)``; a rejection never mutates state."""
        cursor = self._cursor(sub_game)
        if message_type in _AUX_TYPES:
            if step != cursor.step:
                return False, f"auxiliary {message_type} for step {step} != active {cursor.step}"
            return True, ""
        return self._check_core(cursor, step, message_type)

    def _check_core(self, cursor: _SubGameCursor, step: int, message_type: str) -> tuple[bool, str]:
        if step < cursor.step:
            return False, f"stale step {step} < active {cursor.step}"
        if step > cursor.step:
            return False, f"skipped to step {step}; active step is {cursor.step}"
        phase = _CORE_PHASE_INDEX[message_type]
        if message_type == "commitment":
            if cursor.phase != -1:
                return False, f"commitment out of order at step {step} (phase {cursor.phase})"
            cursor.phase = 0
            return True, ""
        if cursor.phase < phase - 1:
            return False, f"{message_type} before its predecessor at step {step}"
        cursor.phase = phase
        if message_type == "reveal":
            cursor.step += 1
            cursor.phase = -1
        return True, ""
