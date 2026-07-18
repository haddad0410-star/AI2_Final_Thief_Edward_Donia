"""Phase 2: peer lifecycle state machine -- legal paths, illegal rejections,
determinism, logging, and terminal/error semantics."""

from __future__ import annotations

import pytest

from thief_peer.domain.state_machine import (
    EventKind,
    IllegalTransitionError,
    PeerState,
    PeerStateMachine,
    TransitionEvent,
)
from thief_peer.domain.state_machine.transitions import resolve

E = EventKind


def _ev(kind: EventKind, detail: str = "") -> TransitionEvent:
    return TransitionEvent(kind=kind, detail=detail)


def _to_signed(m: PeerStateMachine) -> None:
    m.apply(_ev(E.SERVER_STARTED))
    m.apply(_ev(E.BEGIN_NEGOTIATION))
    m.apply(_ev(E.TERMS_SIGNED, detail="config_sha256=abc"))


def test_negotiation_to_signed_path() -> None:
    m = PeerStateMachine()
    assert m.state is PeerState.INITIALIZING
    _to_signed(m)
    assert m.state is PeerState.SIGNED


def test_full_turn_lifecycle() -> None:
    m = PeerStateMachine()
    _to_signed(m)
    m.apply(_ev(E.SUB_GAME_START))
    assert m.state is PeerState.WAITING
    for kind, expected in [
        (E.BEGIN_TURN, PeerState.THINKING),
        (E.MOVE_DECIDED, PeerState.COMMITTING),
        (E.COMMIT_SENT, PeerState.WAITING_FOR_ACK),
        (E.ACK_RECEIVED, PeerState.REVEALING),
        (E.REVEAL_SENT, PeerState.VERIFYING),
        (E.TURN_VERIFIED, PeerState.WAITING),
    ]:
        assert m.apply(_ev(kind)) is expected


def test_sub_game_completion_and_series_completion() -> None:
    m = PeerStateMachine()
    _to_signed(m)
    m.apply(_ev(E.SUB_GAME_START))
    m.apply(_ev(E.BEGIN_TURN))
    m.apply(_ev(E.MOVE_DECIDED))
    m.apply(_ev(E.COMMIT_SENT))
    m.apply(_ev(E.ACK_RECEIVED))
    m.apply(_ev(E.REVEAL_SENT))
    assert m.apply(_ev(E.SUB_GAME_ENDED)) is PeerState.SUB_GAME_OVER
    assert m.apply(_ev(E.BEGIN_AUDIT)) is PeerState.AUDITING
    # loop into another sub-game, then finish the series
    assert m.apply(_ev(E.NEXT_SUB_GAME)) is PeerState.WAITING
    m.apply(_ev(E.BEGIN_TURN))
    m.apply(_ev(E.MOVE_DECIDED))
    m.apply(_ev(E.COMMIT_SENT))
    m.apply(_ev(E.ACK_RECEIVED))
    m.apply(_ev(E.REVEAL_SENT))
    m.apply(_ev(E.SUB_GAME_ENDED))
    m.apply(_ev(E.BEGIN_AUDIT))
    assert m.apply(_ev(E.SERIES_AUDIT_DONE)) is PeerState.SERIES_COMPLETE


def test_error_from_any_state_is_legal() -> None:
    for start in (PeerState.WAITING, PeerState.THINKING, PeerState.VERIFYING):
        m = PeerStateMachine(initial=start)
        assert m.apply(_ev(E.ERROR_OCCURRED, detail="malformed opponent reply")) is PeerState.ERROR


def test_error_is_terminal_except_quit() -> None:
    m = PeerStateMachine(initial=PeerState.ERROR)
    with pytest.raises(IllegalTransitionError):
        m.apply(_ev(E.BEGIN_TURN))
    assert m.apply(_ev(E.QUIT_REQUESTED)) is PeerState.QUIT


def test_clean_quit_from_waiting() -> None:
    m = PeerStateMachine(initial=PeerState.WAITING)
    assert m.apply(_ev(E.QUIT_REQUESTED)) is PeerState.QUIT


def test_terminal_states_reject_everything() -> None:
    for terminal in (PeerState.SERIES_COMPLETE, PeerState.QUIT):
        m = PeerStateMachine(initial=terminal)
        with pytest.raises(IllegalTransitionError):
            m.apply(_ev(E.QUIT_REQUESTED))
        with pytest.raises(IllegalTransitionError):
            m.apply(_ev(E.BEGIN_TURN))


def test_illegal_transition_is_logged_and_rejected() -> None:
    m = PeerStateMachine()
    with pytest.raises(IllegalTransitionError):
        m.apply(_ev(E.MOVE_DECIDED))  # illegal from INITIALIZING
    assert m.state is PeerState.INITIALIZING
    assert len(m.history) == 1
    assert m.history[0].accepted is False
    assert "no transition" in m.history[0].reason


def test_every_accepted_transition_is_logged() -> None:
    m = PeerStateMachine()
    _to_signed(m)
    assert len(m.history) == 3
    assert all(rec.accepted for rec in m.history)
    assert m.history[-1].to_state is PeerState.SIGNED


def test_guard_rejects_terms_signed_without_detail() -> None:
    m = PeerStateMachine()
    m.apply(_ev(E.SERVER_STARTED))
    m.apply(_ev(E.BEGIN_NEGOTIATION))
    with pytest.raises(IllegalTransitionError):
        m.apply(_ev(E.TERMS_SIGNED))  # no config-hash detail
    assert m.state is PeerState.NEGOTIATING


def test_duplicate_event_applied_twice() -> None:
    m = PeerStateMachine()
    m.apply(_ev(E.SERVER_STARTED))
    with pytest.raises(IllegalTransitionError):
        m.apply(_ev(E.SERVER_STARTED))  # already left INITIALIZING
    assert m.state is PeerState.SERVER_READY


def test_out_of_order_event_rejected() -> None:
    m = PeerStateMachine()
    _to_signed(m)
    m.apply(_ev(E.SUB_GAME_START))
    with pytest.raises(IllegalTransitionError):
        m.apply(_ev(E.ACK_RECEIVED))  # ACK before COMMIT
    assert m.state is PeerState.WAITING


def test_resolve_is_pure_and_deterministic() -> None:
    ev = _ev(E.BEGIN_TURN)
    first = resolve(PeerState.WAITING, ev)
    second = resolve(PeerState.WAITING, ev)
    assert first == second == (PeerState.THINKING, "")


def test_force_error_helper() -> None:
    m = PeerStateMachine(initial=PeerState.COMMITTING)
    assert m.force_error("watchdog escalation") is PeerState.ERROR
    assert m.history[-1].event.detail == "watchdog escalation"
