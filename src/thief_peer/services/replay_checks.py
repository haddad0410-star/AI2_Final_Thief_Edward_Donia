"""Per-log and per-score integrity checks for the replay verifier (Phase 12).

Reconstructs each sealed record from a log's step dicts and re-runs the
Phase 4 audit (which recomputes every commitment via
``secrets.compare_digest``, plus nonce-reuse and step-sequence checks). Also
recomputes each declared score from the declared result via the config's
scoring table. Independent implementation (no import of the Police
repository).
"""

from __future__ import annotations

from typing import Any

from thief_peer.domain.captures import SubGameResult
from thief_peer.domain.scoring import score_sub_game
from thief_peer.domain.sealing import (
    SealedRecord,
    SealedTurnPayload,
    audit_sealed_records,
    steps_in_order,
)
from thief_peer.shared.config_sections import Scoring


def payload_from_step(step: dict) -> SealedTurnPayload:
    """Rebuild a :class:`SealedTurnPayload` from one revealed log step."""
    barrier = step.get("barrier_placed")
    claim = step.get("capture_claim")
    return SealedTurnPayload(
        step=step["step"],
        role=step["role"],
        sub_game_number=step["sub_game_number"],
        state=step["state"],
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
        schema_version=step.get("schema_version", "sealed-turn/1"),
    )


def verify_log(log: dict, grid_size: int) -> list[str]:
    """Return findings for one log: commitment/nonce/sequence audit +
    barrier/capture bounds. Any tamper to `claim_response`/`win_claim` is
    already caught by the commit-hash recomputation, since both are part of
    the sealed payload."""
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
    declared_totals = (result["police_total"], result["thief_total"])
    if result.get("agreed") and (police_sum, thief_sum) != declared_totals:
        findings.append("declared totals do not match the sum of sub-game scores")
    return findings
