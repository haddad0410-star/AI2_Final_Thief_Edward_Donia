"""Phase 6: TurnRouter validation -- role/game/config binding, duplicates,
sequence ordering, backpressure, and audit/control handling."""

from __future__ import annotations

from thief_peer.domain.roles import Role
from thief_peer.domain.state_machine import PeerState, PeerStateMachine
from thief_peer.infrastructure.inbox import BoundedInbox
from thief_peer.infrastructure.sequence import SequenceTracker
from thief_peer.infrastructure.turn_router import TurnRouter

UID = "uid-1"
CFG = "c" * 64


def _env(
    step: int = 0,
    sender: str = "police",
    game_uid: str = UID,
    sub_game: int = 1,
    cid: str | None = None,
) -> dict:
    return {
        "schema_version": "1.0",
        "correlation_id": cid or f"corr-{sub_game}-{step}",
        "game_id": "g",
        "game_uid": game_uid,
        "sub_game_number": sub_game,
        "step": step,
        "sender": sender,
        "timestamp": "2026-07-18T00:00:00+00:00",
        "sequence_id": step,
    }


def _commitment(step: int = 0, h: str = "a" * 64, **kw) -> dict:
    return {"envelope": _env(step=step, **kw), "message_type": "commitment", "commit_hash": h}


def _commit_ack(step: int = 0) -> dict:
    return {
        "envelope": _env(step=step, cid=f"ack-{step}"),
        "message_type": "commit_ack",
        "commit_hash": "a" * 64,
    }


def _reveal(step: int = 0) -> dict:
    return {
        "envelope": _env(step=step, cid=f"rev-{step}"),
        "message_type": "reveal",
        "hint_text": "the western routes look risky",
        "hint_intent": "lie",
    }


def _router(**kw) -> TurnRouter:
    return TurnRouter(
        expected_game_uid=UID, expected_sender=Role.POLICE, expected_config_sha256=CFG, **kw
    )


def test_normal_turn_lifecycle_accepted() -> None:
    r = _router()
    assert r.handle_turn(_commitment(0))["ok"] is True
    assert r.handle_turn(_commit_ack(0))["ok"] is True
    assert r.handle_turn(_reveal(0))["ok"] is True
    assert r.handle_turn(_commitment(1))["ok"] is True
    assert r.turn_inbox.size() == 4


def test_duplicate_identical_is_idempotent_ack() -> None:
    r = _router()
    r.handle_turn(_commitment(0))
    ack = r.handle_turn(_commitment(0))
    assert ack["ok"] is True and ack.get("idempotent") is True
    assert r.turn_inbox.size() == 1  # not re-enqueued


def test_duplicate_conflicting_is_rejected() -> None:
    r = _router()
    r.handle_turn(_commitment(0, h="a" * 64))
    ack = r.handle_turn(_commitment(0, h="b" * 64))
    assert ack["ok"] is False and ack["error_code"] == "CONFLICTING_DUPLICATE"


def test_skipped_step_rejected() -> None:
    r = _router()
    ack = r.handle_turn(_commitment(2))  # active step is 0
    assert ack["ok"] is False and ack["error_code"] == "SEQUENCE"
    assert "skipped" in ack["reason"]


def test_out_of_order_reveal_rejected() -> None:
    r = _router()
    ack = r.handle_turn(_reveal(0))  # no commitment first
    assert ack["ok"] is False and ack["error_code"] == "SEQUENCE"


def test_stale_auxiliary_message_rejected() -> None:
    r = _router()
    r.handle_turn(_commitment(0))
    r.handle_turn(_commit_ack(0))
    r.handle_turn(_reveal(0))  # advances active step to 1
    hint_step0 = {
        "envelope": _env(step=0, cid="late-hint"),
        "message_type": "hint",
        "hint_text": "old news",
        "hint_intent": "truth",
    }
    ack = r.handle_turn(hint_step0)
    assert ack["ok"] is False and ack["error_code"] == "SEQUENCE"


def test_wrong_role_rejected() -> None:
    r = _router()
    ack = r.handle_turn(_commitment(0, sender="thief"))
    assert ack["ok"] is False and ack["error_code"] == "WRONG_ROLE"


def test_wrong_game_uid_rejected() -> None:
    r = _router()
    ack = r.handle_turn(_commitment(0, game_uid="other-uid"))
    assert ack["ok"] is False and ack["error_code"] == "WRONG_GAME"


def test_config_mismatch_rejected() -> None:
    r = _router()
    msg = _commitment(0)
    msg["config_sha256"] = "d" * 64
    ack = r.handle_turn(msg)
    assert ack["ok"] is False and ack["error_code"] == "CONFIG_MISMATCH"


def test_malformed_message_rejected() -> None:
    r = _router()
    assert r.handle_turn({"not": "an envelope"})["error_code"] == "MALFORMED"
    assert r.handle_turn({"envelope": _env(), "message_type": "bogus"})["error_code"] == "MALFORMED"
    missing = {"envelope": _env(), "message_type": "commitment"}  # no commit_hash
    assert r.handle_turn(missing)["error_code"] == "MALFORMED"


def test_terminal_lifecycle_rejects_new_turns() -> None:
    machine = PeerStateMachine(initial=PeerState.ERROR)
    r = _router(machine=machine)
    ack = r.handle_turn(_commitment(0))
    assert ack["ok"] is False and ack["error_code"] == "LIFECYCLE"


def test_backpressure_when_inbox_full() -> None:
    small = BoundedInbox(capacity=1)
    r = _router(inbox=small)
    assert r.handle_turn(_commitment(0))["ok"] is True
    r.handle_turn(_commit_ack(0))  # rejected by backpressure (queue full)
    ack = r.handle_turn(_reveal(0))
    assert ack["ok"] is False and ack["error_code"] == "BACKPRESSURE"


def test_capture_claim_and_response_round_trip() -> None:
    r = _router()
    r.handle_turn(_commitment(0))
    claim = {
        "envelope": _env(step=0, cid="claim"),
        "message_type": "capture_claim",
        "claimed_row": 2,
        "claimed_col": 3,
    }
    response = {
        "envelope": _env(step=0, cid="resp"),
        "message_type": "capture_response",
        "caught": False,
    }
    assert r.handle_turn(claim)["ok"] is True
    assert r.handle_turn(response)["ok"] is True


def test_audit_submission_round_trip() -> None:
    r = _router()
    payload = {
        "envelope": _env(step=0, cid="audit"),
        "message_type": "audit",
        "records": [],
        "result_claim": "survival",
    }
    assert r.handle_audit(payload)["ok"] is True
    assert r.handle_audit(payload).get("idempotent") is True
    bad = {"envelope": _env(), "message_type": "not_audit"}
    assert r.handle_audit(bad)["error_code"] == "MALFORMED"


def test_control_message_gracefully_ignored() -> None:
    r = _router()
    ack = r.handle_control({"envelope": _env(), "kind": "status", "status_text": "ready"})
    assert ack["ok"] is True and ack.get("ignored") is True
    assert r.handle_control({"envelope": _env(), "kind": "bogus"})["error_code"] == "MALFORMED"


def test_sequence_tracker_detects_stale_core_step() -> None:
    seq = SequenceTracker()
    assert seq.check_and_advance(1, 0, "commitment")[0] is True
    seq.check_and_advance(1, 0, "commit_ack")
    seq.check_and_advance(1, 0, "reveal")  # -> active step 1
    ok, reason = seq.check_and_advance(1, 0, "commitment")
    assert ok is False and "stale" in reason
