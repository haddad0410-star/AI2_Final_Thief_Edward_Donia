"""Sealing + public-evidence-absorption helpers, split out of ``turn_loop.py``
to keep both files under the 150-meaningful-line cap. Behavior unchanged --
pure decomposition of the same real logic used since Batch 2/3.5.
"""

from __future__ import annotations

from thief_peer.domain.hints import HintIntent
from thief_peer.domain.positions import Direction
from thief_peer.domain.scent import ScentField
from thief_peer.domain.sealing import SealedTurnPayload, new_nonce, seal
from thief_peer.services.subgame_state import SubGameState


def seal_turn(state: SubGameState, direction: Direction, intent: HintIntent, hint: str, deps):
    payload = SealedTurnPayload(
        step=state.step,
        role="thief",
        sub_game_number=state.sub_game_number,
        state=state.state_digest(),
        move=direction.value,
        intent=intent.value,
        hint=hint,
        scent_digest=scent_digest(state.own_scent),
        scent_grid=state.own_scent.grid,
        claim_response=state.pending_claim_response,
        timestamp=deps.now_iso(),
        nonce=new_nonce(),
        config_sha256=deps.config_sha256,
    )
    return seal(payload)


def scent_digest(scent: ScentField) -> str:
    from thief_peer.shared.canonical_json import canonical_sha256_hex

    return canonical_sha256_hex([list(row) for row in scent.grid])


def absorb_public_evidence(state: SubGameState, opp: dict) -> None:
    """Fold the opponent's public reveal into local state: police's real
    scent grid (Batch 3.5 Task 4 -- previously read a ``police_scent`` key
    that does not exist in police's actual reveal dict, which only carries
    ``scent_grid``; see observation_pipeline_audit.md defect B2), and the
    hint's decoded region (Task 5 -- previously never parsed at all)."""
    from thief_peer.domain.hint_region import parse_region_from_hint, region_cells
    from thief_peer.domain.scent_validation import validate_scent_grid

    scent_grid_raw = opp.get("scent_grid")
    if validate_scent_grid(scent_grid_raw, state.grid_size) is None:
        rows = tuple(tuple(float(v) for v in row) for row in scent_grid_raw)
        state.police_scent = ScentField(grid_size=state.grid_size, grid=rows)
    else:
        state.police_scent = None
    hint_text = opp.get("hint")
    region_word = parse_region_from_hint(hint_text) if hint_text else None
    state.hint_region = region_cells(region_word, state.grid_size) if region_word else None
    barrier = opp.get("barrier_placed")
    if barrier is not None:
        from thief_peer.domain.positions import Position

        state.board = state.board.with_barrier(Position(barrier[0], barrier[1]))
