"""The single discriminated, versioned turn message (Batch 2 Phase 6).

Per protocol_contract.md section 2, we use ONE ``message_type``-discriminated
envelope for every per-turn delivery rather than many incompatible tools. This
module validates the *structure* of such a dict (the router adds game-binding,
duplicate, and sequence checks). ``receive_move`` is a compatibility alias that
routes through the exact same validation path.
"""

from __future__ import annotations

#: Every valid discriminator for a turn message.
MESSAGE_TYPES: frozenset[str] = frozenset(
    {
        "commitment",  # H_commit delivery
        "commit_ack",  # acknowledgment of a commitment
        "reveal",  # public move + hint reveal
        "hint",  # standalone hint delivery
        "scent",  # scent payload delivery
        "barrier",  # public barrier declaration (police only)
        "capture_claim",  # police claims a capture
        "capture_response",  # thief's honest response
    }
)

#: Type-specific required fields (in addition to the envelope). ``reveal``'s
#: payload (move/hint/barrier/win_claim/...) is nested under a single
#: ``reveal`` key -- matching the opponent's own wire shape (session recovery
#: step C, Task 5) -- so only that key's presence is checked here; its own
#: internal shape is whatever ``SealedTurnPayload.public_reveal_dict()``
#: produces on either side.
_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "commitment": ("commit_hash",),
    "commit_ack": ("commit_hash",),
    "reveal": ("reveal",),
    "hint": ("hint_text", "hint_intent"),
    "scent": ("grid_size", "grid"),
    "barrier": ("cell_row", "cell_col"),
    "capture_claim": ("claimed_row", "claimed_col"),
    "capture_response": ("caught",),
}

#: ``correlation_id`` is deliberately NOT required here: it is an optional
#: dedup aid (``turn_router.py`` and ``inbox.py`` both treat a missing one as
#: ``""`` and skip correlation-based tracking gracefully), and the Police
#: repo's own envelope builder never sends one at all (session recovery
#: step C, Task 5) -- requiring it here would reject every otherwise-valid
#: message from a compatible, independently-implemented opponent.
_ENVELOPE_FIELDS = (
    "game_uid",
    "sub_game_number",
    "step",
    "sender",
)


def structural_reason(message: dict) -> str | None:
    """Return a rejection reason if `message` is structurally malformed, else
    ``None``. Checks the envelope, the discriminator, and per-type fields."""
    if not isinstance(message, dict):
        return "message must be a JSON object"
    envelope = message.get("envelope")
    if not isinstance(envelope, dict):
        return "missing or non-object envelope"
    for field in _ENVELOPE_FIELDS:
        if field not in envelope:
            return f"envelope missing required field: {field}"
    message_type = message.get("message_type")
    if message_type not in MESSAGE_TYPES:
        return f"unknown message_type: {message_type!r}"
    for field in _REQUIRED_FIELDS[message_type]:
        if field not in message:
            return f"{message_type} message missing field: {field}"
    if message_type == "hint" and message.get("hint_intent") not in ("truth", "lie"):
        return "hint_intent must be 'truth' or 'lie'"
    if message_type == "reveal" and not isinstance(message.get("reveal"), dict):
        return "reveal field must be an object"
    return None
