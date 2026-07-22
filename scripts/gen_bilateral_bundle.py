"""Batch 4B Task 6: write a small, real, valid ``commitment/1`` Thief
artifact bundle to a directory given as argv[1] -- dev/test tooling (like
``print_commitment_vector.py``), not part of the 150-line src/ cap, never
used at runtime by the real peer. Uses this repo's own crypto/artifact
modules for real (no hand-typed hashes), so the output is genuinely
self-verifiable by ``verify-replay``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from thief_peer.domain.sealing import AuditOutcome, AuditReport, SealedTurnPayload, seal
from thief_peer.services.artifact_builders import build_log_artifact
from thief_peer.services.artifact_models import ConfigArtifact, ResultArtifact
from thief_peer.services.artifacts import (
    config_filename,
    log_filename,
    result_filename,
    save_artifact,
)
from thief_peer.shared.canonical_json import canonical_json_bytes
from thief_peer.shared.config_loader import sha256_hex

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "thief" / "game.json"
UID = "bilateral-0000-1111-2222-333344445555"
GID = "batch4b-bilateral"
N_GAMES = 2
STEPS = 3
CONFIG_SHA = sha256_hex(CONFIG_PATH)
TERMS = json.loads(CONFIG_PATH.read_text())


def _payload(sub_game: int, step: int) -> SealedTurnPayload:
    return SealedTurnPayload(
        step=step,
        role="thief",
        sub_game_number=sub_game,
        position=(step, 1),
        move="E",
        barrier_placed=None,
        intent="truth",
        hint="east corridor",
        scent_digest="b" * 8,
        scent_grid=((0.0, 0.0), (0.0, 0.0)),
        capture_claim=None,
        claim_response=True if step == STEPS - 1 else None,
        win_claim=False,
        config_sha256=CONFIG_SHA,
        timestamp="2026-07-22T00:00:00+00:00",
        nonce=f"thief-{sub_game}-{step}-fixed-nonce",
    )


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for n in range(1, N_GAMES + 1):
        recs = tuple(seal(_payload(n, s)) for s in range(STEPS))
        save_artifact(ConfigArtifact(UID, GID, n, CONFIG_SHA, TERMS), out / config_filename(GID, n))
        log = build_log_artifact(
            UID, GID, n, recs, AuditReport(AuditOutcome.VERIFIED, (), (), "ok")
        )
        save_artifact(log, out / log_filename(GID, n))
    sub_games = [
        {
            "sub_game_number": n,
            "result": "capture",
            "winner": "police",
            "police_score": 20,
            "thief_score": 5,
            "steps": STEPS,
            "audit_ok": True,
        }
        for n in range(1, N_GAMES + 1)
    ]
    result = ResultArtifact(
        game_uid=UID,
        game_id=GID,
        git_commit="deadbeef",
        group_id=GID,
        config_sha256=CONFIG_SHA,
        sub_games=sub_games,
        police_total=20 * N_GAMES,
        thief_total=5 * N_GAMES,
        agreement_status="agreed",
        agreed=True,
    )
    save_artifact(result, out / result_filename(GID))
    decl = {"schema_version": "declaration/1", "game_uid": UID, "game_id": GID, "role": "thief"}
    (out / f"declaration_{GID}.json").write_bytes(canonical_json_bytes(decl) + b"\n")
    print(f"wrote bilateral Thief bundle to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
