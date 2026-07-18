"""Typed lifecycle transition events (Batch 2 Phase 2).

An event is a value object: its ``kind`` selects a transition and its optional
``detail`` carries a short human-readable reason/context that is recorded in the
transition log (never game-secret data). Two events with the same kind are
interchangeable for transition purposes, which is what makes duplicate-event and
out-of-order tests meaningful.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EventKind(StrEnum):
    """The kinds of event that can drive a lifecycle transition."""

    SERVER_STARTED = "server_started"
    BEGIN_NEGOTIATION = "begin_negotiation"
    TERMS_SIGNED = "terms_signed"
    SUB_GAME_START = "sub_game_start"
    BEGIN_TURN = "begin_turn"
    MOVE_DECIDED = "move_decided"
    COMMIT_SENT = "commit_sent"
    ACK_RECEIVED = "ack_received"
    REVEAL_SENT = "reveal_sent"
    TURN_VERIFIED = "turn_verified"
    SUB_GAME_ENDED = "sub_game_ended"
    BEGIN_AUDIT = "begin_audit"
    NEXT_SUB_GAME = "next_sub_game"
    SERIES_AUDIT_DONE = "series_audit_done"
    ERROR_OCCURRED = "error_occurred"
    QUIT_REQUESTED = "quit_requested"


@dataclass(frozen=True, slots=True)
class TransitionEvent:
    """One lifecycle event, optionally annotated with a short context string."""

    kind: EventKind
    detail: str = ""
