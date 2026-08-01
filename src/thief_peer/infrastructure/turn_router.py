"""TurnRouter: the validation/routing core behind the FastMCP turn tools.

Every handler is a thin, synchronous "validate then drop into the inbox, ack
immediately" path. It NEVER runs strategy code, never holds the opponent's true
position (this peer never receives it), and never blocks on turn processing --
the local runtime drains the inbox. Lifecycle validity is gated by the Phase 2
state machine (rejecting messages once the peer is terminal/errored); per-turn
ordering is enforced by the SequenceTracker. Every invocation is logged as one
structured JSON record with its accept/reject reason.
"""

from __future__ import annotations

import json
import logging

from thief_peer.domain.roles import Role
from thief_peer.domain.state_machine import PeerState, PeerStateMachine
from thief_peer.infrastructure.inbox import BoundedInbox, InboxFullError
from thief_peer.infrastructure.sequence import SequenceTracker
from thief_peer.protocol.turn_message import structural_reason

logger = logging.getLogger("thief_peer.turn_router")
_DEAD_STATES = frozenset({PeerState.ERROR, PeerState.SERIES_COMPLETE, PeerState.QUIT})
#: A result_agreement audit submission is expected to arrive AFTER this
#: peer's own series has reached SERIES_COMPLETE (the whole point is to
#: exchange final totals once each side is done) -- so it alone is accepted
#: in that one otherwise-dead state; ERROR/QUIT still reject it.
_DEAD_STATES_FOR_AUDIT = frozenset({PeerState.ERROR, PeerState.QUIT})


def _reject(reason: str, code: str) -> dict:
    return {"ok": False, "error_code": code, "reason": reason}


class TurnRouter:
    """Validates and enqueues turn/audit/control messages for one peer."""

    def __init__(
        self,
        *,
        expected_game_uid: str,
        expected_sender: Role,
        expected_config_sha256: str,
        inbox: BoundedInbox | None = None,
        sequence: SequenceTracker | None = None,
        machine: PeerStateMachine | None = None,
    ) -> None:
        self.expected_game_uid = expected_game_uid
        self.expected_sender = expected_sender
        self.expected_config_sha256 = expected_config_sha256
        self.turn_inbox = inbox or BoundedInbox()
        self.audit_inbox = BoundedInbox()
        self.control_inbox = BoundedInbox()
        self.sequence = sequence or SequenceTracker()
        self.machine = machine

    def _log(self, tool: str, envelope: dict, ack: dict) -> None:
        logger.info(
            json.dumps(
                {
                    "tool": tool,
                    "correlation_id": envelope.get("correlation_id", ""),
                    "sub_game": envelope.get("sub_game_number"),
                    "step": envelope.get("step"),
                    "accepted": ack.get("ok", False),
                    "reason": ack.get("reason", ""),
                }
            )
        )

    def _binding_reason(
        self, envelope: dict, message: dict, *, dead_states: frozenset = _DEAD_STATES
    ) -> tuple[str, str] | None:
        if envelope.get("sender") != self.expected_sender.value:
            return f"sender {envelope.get('sender')!r} != expected", "WRONG_ROLE"
        if envelope.get("game_uid") != self.expected_game_uid:
            return "game_uid mismatch", "WRONG_GAME"
        cfg = message.get("config_sha256")
        if cfg is not None and cfg != self.expected_config_sha256:
            return "config_sha256 mismatch", "CONFIG_MISMATCH"
        if self.machine is not None and self.machine.state in dead_states:
            return f"peer is in terminal state {self.machine.state}", "LIFECYCLE"
        return None

    def handle_turn(self, message: dict) -> dict:
        """The receive_turn / receive_move path: full validation + enqueue."""
        ack = self._handle_turn(message)
        self._log(
            "receive_turn", message.get("envelope", {}) if isinstance(message, dict) else {}, ack
        )
        return ack

    def _handle_turn(self, message: dict) -> dict:
        malformed = structural_reason(message)
        if malformed:
            return _reject(malformed, "MALFORMED")
        envelope = message["envelope"]
        binding = self._binding_reason(envelope, message)
        if binding:
            return _reject(binding[0], binding[1])

        sub_game = envelope["sub_game_number"]
        step = envelope["step"]
        mtype = message["message_type"]
        key = f"{sub_game}:{step}:{mtype}"
        if self.turn_inbox.is_idempotent_replay(key, message):
            return {"ok": True, "idempotent": True}
        if self.turn_inbox.is_duplicate_conflict(
            key, message
        ) or self.turn_inbox.correlation_conflict(envelope.get("correlation_id", ""), message):
            return _reject("conflicting duplicate for this logical key", "CONFLICTING_DUPLICATE")

        seq_ok, seq_reason = self.sequence.check_and_advance(sub_game, step, mtype)
        if not seq_ok:
            return _reject(seq_reason, "SEQUENCE")
        try:
            self.turn_inbox.enqueue(key, message, envelope.get("correlation_id", ""))
        except InboxFullError as exc:
            return _reject(str(exc), "BACKPRESSURE")
        return {"ok": True}

    def handle_audit(self, payload: dict) -> dict:
        """The submit_audit path: validate the audit envelope + records, enqueue."""
        ack = self._handle_audit(payload)
        self._log(
            "submit_audit", payload.get("envelope", {}) if isinstance(payload, dict) else {}, ack
        )
        return ack

    def _handle_audit(self, payload: dict) -> dict:
        if not isinstance(payload, dict) or not isinstance(payload.get("envelope"), dict):
            return _reject("missing envelope", "MALFORMED")
        mtype = payload.get("message_type")
        if mtype not in ("audit", "audit_ack", "final_result", "result_agreement"):
            return _reject("unknown audit message_type", "MALFORMED")
        # result_agreement is expected to arrive once THIS peer's own series
        # has already reached SERIES_COMPLETE -- every other audit type
        # keeps the stricter, original dead-state check.
        dead_states = _DEAD_STATES_FOR_AUDIT if mtype == "result_agreement" else _DEAD_STATES
        binding = self._binding_reason(payload["envelope"], payload, dead_states=dead_states)
        if binding:
            return _reject(binding[0], binding[1])
        key = f"audit:{payload['envelope'].get('sub_game_number')}:{mtype}"
        if self.audit_inbox.is_idempotent_replay(key, payload):
            return {"ok": True, "idempotent": True}
        if self.audit_inbox.is_duplicate_conflict(key, payload):
            return _reject("conflicting duplicate for this logical key", "CONFLICTING_DUPLICATE")
        try:
            self.audit_inbox.enqueue(key, payload, payload["envelope"].get("correlation_id", ""))
        except InboxFullError as exc:
            return _reject(str(exc), "BACKPRESSURE")
        return {"ok": True}

    def handle_control(self, message: dict) -> dict:
        """The receive_control path: gracefully-ignored, still validated/enqueued."""
        if not isinstance(message, dict) or "kind" not in message:
            ack = _reject("control message missing 'kind'", "MALFORMED")
        elif message["kind"] not in ("enable", "status", "restart", "quit"):
            ack = _reject(f"invalid control kind {message.get('kind')!r}", "MALFORMED")
        else:
            self.control_inbox.enqueue(f"control:{message.get('kind')}", message)
            ack = {"ok": True, "ignored": True}
        self._log(
            "receive_control", message.get("envelope", {}) if isinstance(message, dict) else {}, ack
        )
        return ack
