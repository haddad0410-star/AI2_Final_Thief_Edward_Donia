"""The transition table, guards, and pure resolution function (Phase 2).

``resolve(state, event)`` is a *pure* function of its inputs: identical
(state, event) pairs always yield the identical result. It returns the next
state, or ``None`` plus a rejection reason for an illegal transition -- it never
mutates anything and never raises.
"""

from __future__ import annotations

from collections.abc import Callable

from thief_peer.domain.state_machine.events import EventKind, TransitionEvent
from thief_peer.domain.state_machine.states import TERMINAL_STATES, PeerState

#: The ordinary (non-wildcard) flow. Keyed by (current state, event kind).
TRANSITIONS: dict[tuple[PeerState, EventKind], PeerState] = {
    (PeerState.INITIALIZING, EventKind.SERVER_STARTED): PeerState.SERVER_READY,
    (PeerState.SERVER_READY, EventKind.BEGIN_NEGOTIATION): PeerState.NEGOTIATING,
    (PeerState.NEGOTIATING, EventKind.TERMS_SIGNED): PeerState.SIGNED,
    (PeerState.SIGNED, EventKind.SUB_GAME_START): PeerState.WAITING,
    (PeerState.WAITING, EventKind.BEGIN_TURN): PeerState.THINKING,
    (PeerState.THINKING, EventKind.MOVE_DECIDED): PeerState.COMMITTING,
    (PeerState.COMMITTING, EventKind.COMMIT_SENT): PeerState.WAITING_FOR_ACK,
    (PeerState.WAITING_FOR_ACK, EventKind.ACK_RECEIVED): PeerState.REVEALING,
    (PeerState.REVEALING, EventKind.REVEAL_SENT): PeerState.VERIFYING,
    (PeerState.VERIFYING, EventKind.TURN_VERIFIED): PeerState.WAITING,
    (PeerState.VERIFYING, EventKind.SUB_GAME_ENDED): PeerState.SUB_GAME_OVER,
    (PeerState.SUB_GAME_OVER, EventKind.BEGIN_AUDIT): PeerState.AUDITING,
    (PeerState.AUDITING, EventKind.NEXT_SUB_GAME): PeerState.WAITING,
    (PeerState.AUDITING, EventKind.SERIES_AUDIT_DONE): PeerState.SERIES_COMPLETE,
}

#: Optional guards: a transition that is present in the table is *additionally*
#: gated by its guard (if any). A guard returning False rejects the transition.
GUARDS: dict[tuple[PeerState, EventKind], Callable[[TransitionEvent], bool]] = {
    # Terms cannot be signed without a concrete config-hash reference in detail.
    (PeerState.NEGOTIATING, EventKind.TERMS_SIGNED): lambda e: bool(e.detail),
}


def resolve(state: PeerState, event: TransitionEvent) -> tuple[PeerState | None, str]:
    """Return ``(next_state, "")`` for a legal transition, or ``(None, reason)``.

    Wildcard rules (checked first): a runtime error moves *any* non-terminal
    state to ERROR; a quit request moves any non-terminal state (including
    ERROR) to QUIT. Everything else consults the table and then the guard.
    """
    if state in TERMINAL_STATES:
        return None, f"{state} is terminal; no transition on {event.kind}"

    if event.kind is EventKind.ERROR_OCCURRED:
        if state is PeerState.ERROR:
            return None, "already in ERROR"
        return PeerState.ERROR, ""

    if event.kind is EventKind.QUIT_REQUESTED:
        return PeerState.QUIT, ""

    if state is PeerState.ERROR:
        return None, f"ERROR only permits QUIT, not {event.kind}"

    target = TRANSITIONS.get((state, event.kind))
    if target is None:
        return None, f"no transition from {state} on {event.kind}"

    guard = GUARDS.get((state, event.kind))
    if guard is not None and not guard(event):
        return None, f"guard rejected {event.kind} from {state}"

    return target, ""
