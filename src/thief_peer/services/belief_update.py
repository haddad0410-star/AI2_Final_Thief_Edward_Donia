"""Local belief maintenance for the sub-game runtime (Batch 2 Phase 9).

Frozen turn-level update order (Batch 3.5 Task 6, see
``docs/BELIEF_MODEL.md``): prior belief -> legal transition prediction ->
barrier/impossible-cell masking -> newest scent likelihood -> newest hint
likelihood -> normalization. None of these inputs is the opponent's true
position.
"""

from __future__ import annotations

from collections.abc import Iterable

from thief_peer.domain.belief_model import BeliefMap, entropy
from thief_peer.domain.belief_updates import (
    apply_barrier_mask,
    apply_hint_likelihood,
    apply_scent_likelihood,
    apply_transition,
)
from thief_peer.domain.board import Board
from thief_peer.domain.positions import Position
from thief_peer.domain.scent import ScentField

#: Bounded trust adjustment rates: a hint that sharpens belief (entropy
#: drops) earns trust slowly; one that contradicts it (entropy rises) loses
#: trust faster -- consistency history stands in for the sealed intent
#: verdict, which must never be used for this (Batch 3.5 Task 5).
_TRUST_GAIN = 0.08
_TRUST_LOSS = 0.12
_TRUST_FLOOR = 0.05
_TRUST_CEILING = 0.95


def _update_hint_trust(current_trust: float, entropy_before: float, entropy_after: float) -> float:
    if entropy_after < entropy_before - 1e-9:
        return min(_TRUST_CEILING, current_trust + _TRUST_GAIN * (1.0 - current_trust))
    if entropy_after > entropy_before + 1e-9:
        return max(_TRUST_FLOOR, current_trust - _TRUST_LOSS * current_trust)
    return current_trust


def update_belief(
    belief: BeliefMap,
    board: Board,
    police_scent: ScentField | None,
    hint_region: Iterable[Position] | None,
    hint_trust: float = 0.5,
) -> tuple[BeliefMap, float]:
    """One turn's belief update about where the police is; returns the
    updated belief and the updated hint-trust score.

    Predict via a legal-neighbour diffusion, mask barriers, then fold in the
    police's public scent (if received) and hint region (down-weighted by
    agreement inside :func:`apply_hint_likelihood`)."""
    predicted = apply_transition(belief, board.adjacent_cells)
    masked = apply_barrier_mask(predicted, board.barriers)
    if police_scent is not None:
        masked = apply_scent_likelihood(masked, police_scent)
    new_trust = hint_trust
    if hint_region is not None:
        entropy_before_hint = entropy(masked)
        masked = apply_hint_likelihood(masked, hint_region, hint_trust)
        new_trust = _update_hint_trust(hint_trust, entropy_before_hint, entropy(masked))
    return masked, new_trust
