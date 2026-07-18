"""Local belief maintenance for the sub-game runtime (Batch 2 Phase 9).

Wraps the Batch 1 belief primitives into the per-turn update the runtime needs:
predict (diffuse over legal neighbours), then fold in the police's own PUBLIC
scent grid and hint region. None of these inputs is the opponent's true position.
"""

from __future__ import annotations

from collections.abc import Iterable

from thief_peer.domain.belief_model import BeliefMap
from thief_peer.domain.belief_updates import (
    apply_barrier_mask,
    apply_hint_likelihood,
    apply_scent_likelihood,
    apply_transition,
)
from thief_peer.domain.board import Board
from thief_peer.domain.positions import Position
from thief_peer.domain.scent import ScentField


def update_belief(
    belief: BeliefMap,
    board: Board,
    police_scent: ScentField | None,
    hint_region: Iterable[Position] | None,
) -> BeliefMap:
    """One turn's belief update about where the police is.

    Predict via a legal-neighbour diffusion, mask barriers, then fold in the
    police's public scent (if received) and hint region (down-weighted by
    agreement inside :func:`apply_hint_likelihood`)."""
    predicted = apply_transition(belief, board.adjacent_cells)
    masked = apply_barrier_mask(predicted, board.barriers)
    if police_scent is not None:
        masked = apply_scent_likelihood(masked, police_scent)
    if hint_region is not None:
        masked = apply_hint_likelihood(masked, hint_region)
    return masked
