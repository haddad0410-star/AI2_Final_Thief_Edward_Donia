"""The peer lifecycle states (Batch 2 Phase 2).

Restart / recovery semantics (binding decision, see docs/adr/ADR-0013):
- ``SERIES_COMPLETE`` and ``QUIT`` are fully terminal: no outgoing transition.
- ``ERROR`` is a terminal *outcome* for gameplay -- the only transition it
  permits is ``QUIT`` (to record a clean process exit after a technical loss).
- ``INITIALIZING`` can never be re-entered. Recovery from ``ERROR`` is an
  out-of-process concern (construct a fresh machine / restart the peer), never an
  in-machine loop -- this is what makes the machine free of restart cycles.
"""

from __future__ import annotations

from enum import StrEnum


class PeerState(StrEnum):
    """Every distinct lifecycle state a peer process can occupy."""

    INITIALIZING = "initializing"
    SERVER_READY = "server_ready"
    NEGOTIATING = "negotiating"
    SIGNED = "signed"
    WAITING = "waiting"
    THINKING = "thinking"
    COMMITTING = "committing"
    WAITING_FOR_ACK = "waiting_for_ack"
    REVEALING = "revealing"
    VERIFYING = "verifying"
    SUB_GAME_OVER = "sub_game_over"
    AUDITING = "auditing"
    SERIES_COMPLETE = "series_complete"
    ERROR = "error"
    QUIT = "quit"


#: States with no outgoing transitions at all.
TERMINAL_STATES: frozenset[PeerState] = frozenset({PeerState.SERIES_COMPLETE, PeerState.QUIT})
