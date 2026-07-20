"""SealedTurnPayload: the versioned, canonical per-step record (Batch 2 Phase 4;
scent/intent sealing repaired Batch 3.5 Task 4/5 -- see
integration_lab/evidence/batch3_5/observation_pipeline_audit.md defects A1/C2).

This is the exact structure that is SHA-256 sealed at commit time and revealed
(with its nonce and intent) at the final audit. Every field is either this
peer's own truth or legally-public information -- there is NO
opponent-true-position field, by construction (see
tests/security/test_sealed_payload_isolation.py). The thief may lie only in
``hint`` (with ``intent`` honestly declaring truth/lie, sealed until the
final audit); every physical/cryptographic field is honest.

The binding protocol field set (protocol_contract.md section 3.2) names the
actual scent trail (``smell_grid``) as a sealed field, not merely a digest of
it -- ``scent_grid`` carries the real values; ``scent_digest`` remains as an
additional stable-digest convenience field.
"""

from __future__ import annotations

from dataclasses import dataclass

CURRENT_SCHEMA_VERSION = "sealed-turn/2"


@dataclass(frozen=True, slots=True)
class SealedTurnPayload:
    """One step's fully-sealable record. Canonicalized before hashing."""

    step: int
    role: str
    sub_game_number: int
    state: str
    move: str | None
    intent: str
    hint: str
    scent_digest: str
    scent_grid: tuple[tuple[float, ...], ...]
    timestamp: str
    nonce: str
    config_sha256: str
    barrier_placed: tuple[int, int] | None = None
    capture_claim: tuple[int, int] | None = None
    claim_response: bool | None = None
    win_claim: bool = False
    schema_version: str = CURRENT_SCHEMA_VERSION

    def to_canonical_dict(self) -> dict:
        """A JSON-serializable dict (tuples -> lists) with every sealed field.

        The dict is hashed via ``canonical_json`` (sorted keys), so key order
        here is irrelevant; what matters is that the field *set* and *values*
        are exactly reproduced at audit time by whoever recomputes the hash.
        """
        return {
            "schema_version": self.schema_version,
            "step": self.step,
            "role": self.role,
            "sub_game_number": self.sub_game_number,
            "state": self.state,
            "move": self.move,
            "intent": self.intent,
            "hint": self.hint,
            "scent_digest": self.scent_digest,
            "scent_grid": [list(row) for row in self.scent_grid],
            "barrier_placed": list(self.barrier_placed) if self.barrier_placed else None,
            "capture_claim": list(self.capture_claim) if self.capture_claim else None,
            "claim_response": self.claim_response,
            "win_claim": self.win_claim,
            "config_sha256": self.config_sha256,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
        }

    def public_reveal_dict(self) -> dict:
        """The fields revealed in the clear at REVEAL time -- everything
        except ``nonce`` and ``intent`` (both stay hidden until the final
        audit; ``intent`` -- the hint's truth/lie verdict -- must stay
        sealed during play per the absolute rule "truth/lie intent sealed",
        so a receiver judges hint reliability from consistency history, not
        an early-disclosed verdict)."""
        data = self.to_canonical_dict()
        del data["nonce"]
        del data["intent"]
        return data
