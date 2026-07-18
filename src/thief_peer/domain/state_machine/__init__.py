"""Explicit peer lifecycle state machine (Batch 2 Phase 2).

Public surface: the state/event enums, the typed event, the machine, and its
rejection exception. All lifecycle changes must route through
:class:`PeerStateMachine`; nothing may mutate a "current state" field directly.
"""

from __future__ import annotations

from thief_peer.domain.state_machine.events import EventKind, TransitionEvent
from thief_peer.domain.state_machine.machine import (
    IllegalTransitionError,
    PeerStateMachine,
    TransitionLog,
)
from thief_peer.domain.state_machine.states import TERMINAL_STATES, PeerState

__all__ = [
    "TERMINAL_STATES",
    "EventKind",
    "IllegalTransitionError",
    "PeerState",
    "PeerStateMachine",
    "TransitionEvent",
    "TransitionLog",
]
