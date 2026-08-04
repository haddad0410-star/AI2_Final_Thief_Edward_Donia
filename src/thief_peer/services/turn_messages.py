"""Wire-message builders for the thief's outbound turn (Batch 2 Phase 9;
envelope/reveal shape aligned to the Police repo's wire contract in session
recovery step C, Task 5 -- see
``_post4b_supplementary_evidence/audit/protocol_contract.md``
section 3.3/"sequence_id" note).

Produces the discriminated ``message_type`` envelopes the opponent's
``receive_turn`` expects. The commitment carries only ``H_commit``; the reveal
carries the full public payload (move, hint, barrier, win_claim, ...) in the
clear but never the nonce, nested under a ``reveal`` key -- matching the
opponent's own wire shape so either side's parser reads the other's message
without a shape-specific special case.

``sequence_id`` is a strictly-monotonic counter across every core-phase
(commitment/reveal) message sent in one sub-game, starting at 0 for the first
commitment -- NOT the same value as the logical game ``step`` (which stays
constant across a commit+reveal pair). Each step consumes exactly two
sequence numbers: ``2 * step`` for the commitment, ``2 * step + 1`` for the
reveal.
"""

from __future__ import annotations

from thief_peer.domain.sealing import SealedRecord


def _envelope(
    game_uid: str, sub_game: int, step: int, sequence_id: int, corr: str, timestamp: str
) -> dict:
    return {
        "schema_version": "1.0",
        "correlation_id": corr,
        "game_id": game_uid,
        "game_uid": game_uid,
        "sub_game_number": sub_game,
        "step": step,
        "sender": "thief",
        "timestamp": timestamp,
        "sequence_id": sequence_id,
    }


def commitment_message(record: SealedRecord, game_uid: str, config_sha256: str) -> dict:
    """The commit-phase message: publishes only the SHA-256 commitment."""
    payload = record.payload
    return {
        "envelope": _envelope(
            game_uid,
            payload.sub_game_number,
            payload.step,
            2 * payload.step,
            f"commit-{payload.sub_game_number}-{payload.step}",
            payload.timestamp,
        ),
        "message_type": "commitment",
        "commit_hash": record.commit_hash,
        "config_sha256": config_sha256,
    }


def reveal_message(record: SealedRecord, game_uid: str, config_sha256: str) -> dict:
    """The reveal-phase message: full public payload in the clear (nonce
    withheld), nested under ``reveal`` to match the opponent's wire shape."""
    payload = record.payload
    return {
        "envelope": _envelope(
            game_uid,
            payload.sub_game_number,
            payload.step,
            2 * payload.step + 1,
            f"reveal-{payload.sub_game_number}-{payload.step}",
            payload.timestamp,
        ),
        "message_type": "reveal",
        "reveal": payload.public_reveal_dict(),
        "config_sha256": config_sha256,
    }
