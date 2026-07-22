"""SealedTurnPayload: the versioned, canonical per-step record.

Batch 4B Task 3: the sealed field set is now ``commitment/1`` -- a single,
role-agnostic canonical shape both this repo and the independently-built
Police repo adopt for newly-sealed records, resolving the divergence
documented in
``integration_lab/evidence/batch4b/commitment_schema_audit.md`` (this
repo's ``state`` field was an opaque string digest, `"pos=R,C;visited=N"`,
that Police's verifier could never parse as a position). Fixed by
replacing ``state`` with a plain ``position`` tuple -- this repo's
``config_sha256`` was already a top-level field (Police's was nested
inside ``state``; Police adopted this repo's convention). See
``integration_lab/evidence/batch4b/canonical_commitment_design.md`` for
the full design rationale.

Legacy note: records sealed under the prior ``sealed-turn/2`` schema
(Batch 1-4A evidence) are UNCHANGED on disk and remain self-verifiable by
this repo under their own original schema
(``services/replay_checks.py::payload_from_step`` still reconstructs them
correctly) -- only NEWLY sealed records use ``commitment/1``.

Every field is either this peer's own truth or legally-public information
-- there is NO opponent-true-position field, by construction (see
tests/security/test_sealed_payload_isolation.py). The thief may lie only in
``hint`` (with ``intent`` honestly declaring truth/lie, sealed until the
final audit); every physical/cryptographic field is honest.
"""

from __future__ import annotations

from dataclasses import dataclass

CURRENT_SCHEMA_VERSION = "commitment/1"

#: The exact field set of a ``commitment/1`` canonical dict -- used to
#: reject unknown fields that could otherwise silently alter a commitment.
CANONICAL_FIELD_SET = frozenset(
    {
        "schema_version",
        "step",
        "role",
        "sub_game_number",
        "position",
        "move",
        "intent",
        "hint",
        "scent_digest",
        "scent_grid",
        "barrier_placed",
        "capture_claim",
        "claim_response",
        "win_claim",
        "config_sha256",
        "timestamp",
        "nonce",
    }
)


@dataclass(frozen=True, slots=True)
class SealedTurnPayload:
    """One step's fully-sealable record (``commitment/1``). Canonicalized
    before hashing."""

    step: int
    role: str
    sub_game_number: int
    position: tuple[int, int]
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
    #: The EXACT original ``state`` digest string from a legacy
    #: ``sealed-turn/1``/``/2`` record (e.g. ``"pos=3,4;visited=2"`` -- the
    #: visited count is real per-step state this dataclass no longer
    #: tracks, so it must be carried through verbatim, not re-derived, or
    #: legacy hash recomputation would silently corrupt it). ``None`` for
    #: any ``commitment/1`` payload.
    legacy_state: str | None = None

    def to_canonical_dict(self) -> dict:
        """A JSON-serializable dict (tuples -> lists) with every sealed field.

        The dict is hashed via ``canonical_json`` (sorted keys), so key order
        here is irrelevant; what matters is that the field *set* and *values*
        are exactly reproduced at audit time by whoever recomputes the hash.
        Schema-version aware: a record reconstructed from LEGACY
        ``sealed-turn/1``/``/2`` evidence must canonicalize back into that
        legacy shape (string ``state``) so its original commitment hash
        still recomputes correctly -- only ``commitment/1`` uses the new
        flat ``position`` shape. This is what keeps Batch 1-4A evidence
        self-verifiable without rewriting any file on disk.
        """
        if self.schema_version in ("sealed-turn/1", "sealed-turn/2"):
            row, col = self.position
            state = (
                self.legacy_state if self.legacy_state is not None else f"pos={row},{col};visited=1"
            )
            return {
                "schema_version": self.schema_version,
                "step": self.step,
                "role": self.role,
                "sub_game_number": self.sub_game_number,
                "state": state,
                "move": self.move,
                "intent": self.intent,
                "hint": self.hint,
                "scent_digest": self.scent_digest,
                "scent_grid": [list(row_) for row_ in self.scent_grid],
                "barrier_placed": list(self.barrier_placed) if self.barrier_placed else None,
                "capture_claim": list(self.capture_claim) if self.capture_claim else None,
                "claim_response": self.claim_response,
                "win_claim": self.win_claim,
                "config_sha256": self.config_sha256,
                "timestamp": self.timestamp,
                "nonce": self.nonce,
            }
        return {
            "schema_version": self.schema_version,
            "step": self.step,
            "role": self.role,
            "sub_game_number": self.sub_game_number,
            "position": list(self.position),
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
