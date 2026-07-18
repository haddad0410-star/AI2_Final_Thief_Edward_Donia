"""Wire-message builders for the thief's outbound turn (Batch 2 Phase 9).

Produces the discriminated ``message_type`` envelopes the opponent's
``receive_turn`` expects. The commitment carries only ``H_commit``; the reveal
carries the move + hint in the clear but never the nonce.
"""

from __future__ import annotations

from thief_peer.domain.sealing import SealedRecord


def _envelope(game_uid: str, sub_game: int, step: int, corr: str, timestamp: str) -> dict:
    return {
        "schema_version": "1.0",
        "correlation_id": corr,
        "game_id": game_uid,
        "game_uid": game_uid,
        "sub_game_number": sub_game,
        "step": step,
        "sender": "thief",
        "timestamp": timestamp,
        "sequence_id": step,
    }


def commitment_message(record: SealedRecord, game_uid: str, config_sha256: str) -> dict:
    """The commit-phase message: publishes only the SHA-256 commitment."""
    payload = record.payload
    return {
        "envelope": _envelope(
            game_uid,
            payload.sub_game_number,
            payload.step,
            f"commit-{payload.sub_game_number}-{payload.step}",
            payload.timestamp,
        ),
        "message_type": "commitment",
        "commit_hash": record.commit_hash,
        "config_sha256": config_sha256,
    }


def reveal_message(record: SealedRecord, game_uid: str, config_sha256: str) -> dict:
    """The reveal-phase message: move + hint in the clear, nonce still hidden."""
    payload = record.payload
    return {
        "envelope": _envelope(
            game_uid,
            payload.sub_game_number,
            payload.step,
            f"reveal-{payload.sub_game_number}-{payload.step}",
            payload.timestamp,
        ),
        "message_type": "reveal",
        "move": payload.move,
        "hint_text": payload.hint,
        "hint_intent": payload.intent,
        "config_sha256": config_sha256,
    }
