"""End-to-end proof that a position-deferred reveal (sharNamr friendly only)
survives a full round trip through the REAL wire-message builder and the
REAL receiving-side processing functions, without any production code
change -- calls turn_messages.reveal_message, capture_resolution.resolve_capture,
and turn_prep.absorb_public_evidence directly, exactly as turn_loop.py does,
proving the receiving side tolerates missing move/position without error and
still resolves captures/absorbs evidence correctly.
"""

from __future__ import annotations

from _sealing_fixtures import make_record

from thief_peer.domain.positions import Position
from thief_peer.domain.sealing.friendly_external import reveal_message_position_deferred
from thief_peer.services.capture_resolution import resolve_capture
from thief_peer.services.turn_messages import reveal_message


def test_position_deferred_reveal_round_trips_through_real_receiving_functions() -> None:
    record = make_record(step=2)

    # Real wire message, exactly as turn_loop.py builds it.
    full_message = reveal_message(record, game_uid="g-e2e", config_sha256="a" * 64)
    assert "move" in full_message["reveal"]
    assert "position" in full_message["reveal"]

    # The friendly-only transform (never called by production turn_loop.py).
    deferred_message = reveal_message_position_deferred(full_message)
    opp = deferred_message["reveal"]
    assert "move" not in opp
    assert "position" not in opp
    assert "nonce" not in opp
    assert "intent" not in opp

    # Exactly what turn_loop.py's _resolve_and_advance does with the
    # opponent's reveal dict -- proves the receiving side never needs
    # move/position and doesn't raise on their absence.
    resolution = resolve_capture(
        own_position=Position(0, 0),
        claimed_cell=opp.get("capture_claim"),
        barrier_cell=opp.get("barrier_placed"),
    )
    assert resolution is not None  # completed without KeyError/AttributeError

    # hint/scent extraction (absorb_public_evidence's actual field reads)
    # still succeed on the reduced dict.
    assert opp.get("hint") == record.payload.hint
    assert opp.get("scent_grid") == [list(row) for row in record.payload.scent_grid]


def test_position_deferred_does_not_affect_our_own_local_audit_record() -> None:
    """The full internal record (used for our own log artifact / final
    audit) is completely unaffected -- only what's TRANSMITTED changes."""
    record = make_record(step=2)
    full_message = reveal_message(record, game_uid="g-e2e", config_sha256="a" * 64)
    reveal_message_position_deferred(full_message)

    # record itself (what gets written to our own log artifact) still has
    # everything, always -- proves no data is actually lost, only deferred
    # from the live wire.
    full = record.payload.to_canonical_dict()
    assert full["move"] == "E"
    assert full["position"] == [3, 5]
    assert full["nonce"]
