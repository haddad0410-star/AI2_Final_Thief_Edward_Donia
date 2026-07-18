"""PeerStateMachine: the single, authoritative lifecycle owner (Phase 2).

Every lifecycle change in the peer flows through :meth:`PeerStateMachine.apply`.
FastMCP tool handlers (Phase 6) call this; strategy code (Phase 7) is never given
a reference to it, so it structurally cannot alter lifecycle state. Every attempt
-- accepted or rejected -- is appended to the structured transition log; illegal
attempts raise :class:`IllegalTransitionError` (they are logged first, never
silently ignored).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from thief_peer.domain.state_machine.events import TransitionEvent
from thief_peer.domain.state_machine.states import PeerState
from thief_peer.domain.state_machine.transitions import resolve


class IllegalTransitionError(Exception):
    """Raised when an event is not a legal transition from the current state."""


@dataclass(frozen=True, slots=True)
class TransitionLog:
    """One immutable record of a transition attempt (accepted or rejected)."""

    index: int
    from_state: PeerState
    event: TransitionEvent
    to_state: PeerState | None
    accepted: bool
    reason: str
    at_seq: int


class PeerStateMachine:
    """A deterministic lifecycle machine with a structured transition log."""

    def __init__(
        self,
        initial: PeerState = PeerState.INITIALIZING,
        seq_fn: Callable[[], int] | None = None,
    ) -> None:
        self._state = initial
        self._history: list[TransitionLog] = []
        self._seq_fn = seq_fn or (lambda: len(self._history))

    @property
    def state(self) -> PeerState:
        """The current lifecycle state."""
        return self._state

    @property
    def history(self) -> tuple[TransitionLog, ...]:
        """The full, append-only transition log (accepted and rejected)."""
        return tuple(self._history)

    def can_apply(self, event: TransitionEvent) -> bool:
        """True iff `event` would be accepted right now (no mutation)."""
        target, _ = resolve(self._state, event)
        return target is not None

    def apply(self, event: TransitionEvent) -> PeerState:
        """Apply `event`, returning the new state. Logs the attempt either way;
        raises :class:`IllegalTransitionError` on an illegal transition."""
        target, reason = resolve(self._state, event)
        record = TransitionLog(
            index=len(self._history),
            from_state=self._state,
            event=event,
            to_state=target,
            accepted=target is not None,
            reason=reason,
            at_seq=self._seq_fn(),
        )
        self._history.append(record)
        if target is None:
            raise IllegalTransitionError(reason)
        self._state = target
        return target

    def force_error(self, detail: str = "") -> PeerState:
        """Convenience for the runtime error path: transition to ERROR from any
        non-terminal state (a no-op-safe legal transition)."""
        from thief_peer.domain.state_machine.events import EventKind

        return self.apply(TransitionEvent(kind=EventKind.ERROR_OCCURRED, detail=detail))
