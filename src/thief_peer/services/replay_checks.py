"""Per-log and per-score integrity checks for the replay verifier (Phase 12).

Reconstructs each sealed record from a log's step dicts and re-runs the
Phase 4 audit (which recomputes every commitment via
``secrets.compare_digest``, plus nonce-reuse and step-sequence checks). Also
recomputes each declared score from the declared result via the config's
scoring table. Independent implementation (no import of the Police
repository).

Batch 4B Task 3/4: ``payload_from_step`` now handles both the current
``commitment/1`` shape (a top-level ``position``, bilaterally verifiable --
see ``_post4b_supplementary_evidence/batch4b/commitment_schema_audit.md``) and
the legacy ``sealed-turn/1``/``/2`` shape (Batch 1-4A evidence, where
``state`` was an opaque digest string), so old evidence remains
self-verifiable under its own original schema. Because the field SET is
now unified, this same reconstruction also correctly rebuilds a genuine
Police ``commitment/1`` record -- no opposite-repo import needed.
"""

from __future__ import annotations

import re
from typing import Any

from thief_peer.domain.captures import SubGameResult
from thief_peer.domain.scoring import score_sub_game
from thief_peer.domain.sealing import (
    SealedRecord,
    SealedTurnPayload,
    audit_sealed_records,
    steps_in_order,
)
from thief_peer.domain.sealing.payload import CANONICAL_FIELD_SET, CURRENT_SCHEMA_VERSION
from thief_peer.shared.config_sections import Scoring

#: Bookkeeping keys allowed alongside the canonical commitment fields in a
#: log-artifact step (added by the log writer, never part of H_commit).
_LOG_STEP_EXTRA_KEYS = frozenset({"commit_hash"})

_LEGACY_STATE_RE = re.compile(r"pos=(-?\d+),(-?\d+)")


def _position_from_legacy_state(state: str) -> tuple[int, int]:
    m = _LEGACY_STATE_RE.search(state)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def payload_from_step(step: dict) -> SealedTurnPayload:
    """Rebuild a :class:`SealedTurnPayload` from one revealed log step.

    A record is only ever reconstructed using the schema it declares; the
    new and legacy shapes are never mixed.
    """
    barrier = step.get("barrier_placed")
    claim = step.get("capture_claim")
    schema_version = step.get("schema_version", "sealed-turn/1")
    legacy_state = None
    if "position" in step:
        position = tuple(step["position"])
    else:  # legacy sealed-turn/1 or /2: own cell was encoded in a "state" digest string
        legacy_state = step.get("state", "")
        position = _position_from_legacy_state(legacy_state)
    return SealedTurnPayload(
        step=step["step"],
        role=step["role"],
        sub_game_number=step["sub_game_number"],
        position=position,
        legacy_state=legacy_state,
        move=step["move"],
        barrier_placed=tuple(barrier) if barrier else None,
        capture_claim=tuple(claim) if claim else None,
        claim_response=step.get("claim_response"),
        win_claim=step.get("win_claim", False),
        intent=step["intent"],
        hint=step["hint"],
        scent_digest=step["scent_digest"],
        scent_grid=tuple(tuple(row) for row in step["scent_grid"]) if "scent_grid" in step else (),
        timestamp=step["timestamp"],
        nonce=step["nonce"],
        config_sha256=step["config_sha256"],
        schema_version=schema_version,
    )


def _check_role_fields(step: dict, number, findings: list[str]) -> None:
    """Batch 4B Task 6: a role-specific field placed on the wrong role is a
    real tamper, not a stylistic issue -- Thief must never carry a
    Police-only ``barrier_placed``/``capture_claim`` value, and Police must
    never carry a Thief-only ``claim_response``/``win_claim`` value."""
    role, step_no = step.get("role"), step.get("step")
    if role == "thief":
        if step.get("barrier_placed") is not None:
            findings.append(
                f"sub-game {number} step {step_no}: thief record has barrier_placed set"
            )
        if step.get("capture_claim") is not None:
            findings.append(f"sub-game {number} step {step_no}: thief record has capture_claim set")
    elif role == "police":
        if step.get("claim_response") is not None:
            findings.append(
                f"sub-game {number} step {step_no}: police record has claim_response set"
            )
        if step.get("win_claim"):
            findings.append(f"sub-game {number} step {step_no}: police record has win_claim=true")


def _check_unknown_fields(step: dict, number, findings: list[str]) -> None:
    """Batch 4B Task 3: reject unknown fields on a current-schema record --
    an extra key could otherwise silently alter what the receiver thinks
    was committed."""
    if step.get("schema_version") != CURRENT_SCHEMA_VERSION:
        return
    extra = set(step) - CANONICAL_FIELD_SET - _LOG_STEP_EXTRA_KEYS
    if extra:
        findings.append(
            f"sub-game {number} step {step.get('step')}: unknown field(s) {sorted(extra)}"
        )


def verify_log(log: dict, grid_size: int) -> list[str]:
    """Return findings for one log: commitment/nonce/sequence audit +
    barrier/capture bounds + role-field consistency + unknown-field
    rejection. Any tamper to `claim_response`/`win_claim` is already caught
    by the commit-hash recomputation, since both are part of the sealed
    payload."""
    findings: list[str] = []
    number = log.get("sub_game_number", "?")
    records = [SealedRecord(payload_from_step(s), s["commit_hash"]) for s in log["steps"]]
    audit = audit_sealed_records(records)
    if not audit.verified:
        findings.append(f"sub-game {number}: {audit.reason}")
    if not steps_in_order(records):
        findings.append(f"sub-game {number}: step sequence not contiguous/ascending")
    for step in log["steps"]:
        for name in ("barrier_placed", "capture_claim"):
            cell = step.get(name)
            if cell is not None and not (0 <= cell[0] < grid_size and 0 <= cell[1] < grid_size):
                findings.append(f"sub-game {number}: {name} {cell} out of bounds")
        _check_role_fields(step, number, findings)
        _check_unknown_fields(step, number, findings)
    return findings


def scoring_from_terms(terms: dict[str, Any]) -> Scoring:
    """Build a :class:`Scoring` from the config artifact's terms (ignores _notes)."""
    raw = {k: v for k, v in terms["scoring"].items() if not k.startswith("_")}
    return Scoring(**raw)


def verify_scores(result: dict, scoring: Scoring) -> list[str]:
    """Recompute each declared score from its result and check the totals."""
    findings: list[str] = []
    police_sum = 0
    thief_sum = 0
    for entry in result["sub_games"]:
        outcome = SubGameResult(entry["result"])
        expected = score_sub_game(outcome, scoring)
        declared = (entry["police_score"], entry["thief_score"])
        if declared != expected:
            findings.append(f"sub-game {entry['sub_game_number']}: score {declared} != {expected}")
        police_sum += entry["police_score"]
        thief_sum += entry["thief_score"]
    # This is THIS side's own internal self-consistency check (post-Batch-4B
    # fix). Previously gated on `result.get("agreed")`, which was masked as
    # always-true by the "agreed=True merely because completed" bug this
    # batch fixes -- gating tamper detection on that same buggy flag would
    # have silently stopped catching a tampered total the moment the flag
    # became honest. A genuinely disputed series legitimately reports
    # zeroed totals (never the real sum) by design; every other status
    # (agreed, or an unconfirmed but still internally-honest
    # unverified_self_play) must still match the real per-sub-game sum.
    declared_totals = (result["police_total"], result["thief_total"])
    if result.get("agreement_status") == "disputed_zeroed":
        if declared_totals != (0, 0):
            findings.append("disputed_zeroed result must report zeroed totals")
    elif (police_sum, thief_sum) != declared_totals:
        findings.append("declared totals do not match the sum of sub-game scores")
    return findings
