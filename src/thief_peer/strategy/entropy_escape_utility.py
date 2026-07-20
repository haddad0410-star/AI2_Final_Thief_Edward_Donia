"""Scoring helpers for :class:`EntropyEscapeThiefBrain` (Batch 3, Task 4).

Every function here is a pure function of PUBLIC information already
carried on a :class:`~thief_peer.strategy.decision.ThiefDecisionInput` (own
position, belief, board, visited set) -- none accepts or could accept an
opponent-true-position argument.
"""

from __future__ import annotations

from collections import deque

from thief_peer.domain.belief_model import BeliefMap, expected_distance, top_k
from thief_peer.domain.belief_updates import apply_transition
from thief_peer.domain.board import Board
from thief_peer.domain.positions import Position
from thief_peer.strategy.entropy_escape_config import EntropyEscapeWeights


def manhattan(a: Position, b: Position) -> int:
    return abs(a.row - b.row) + abs(a.col - b.col)


def _neighbors_including_stay(board: Board):
    def fn(p: Position):
        if board.is_barrier(p):
            return ()
        return (p, *(c for c in board.adjacent_cells(p) if not board.is_barrier(c)))

    return fn


def project_belief(belief: BeliefMap, board: Board, depth: int) -> BeliefMap:
    """Bounded lookahead (Task 4F): spread ``belief`` (this peer's belief
    about the OPPONENT) forward ``depth`` legal transition steps, using the
    same ``apply_transition`` primitive the real belief pipeline uses."""
    projected = belief
    neighbors_fn = _neighbors_including_stay(board)
    for _ in range(max(0, depth)):
        projected = apply_transition(projected, neighbors_fn)
    return projected


def reachable_area(board: Board, start: Position, limit: int = 30) -> int:
    """Bounded BFS flood-fill cell count reachable from ``start`` -- the
    real (not hand-waved) measure behind "reachable-region size" /
    "mobility preservation" (Task 4B). Bounded so a large open board never
    costs more than ``limit`` expansions per candidate move."""
    if board.is_barrier(start):
        return 0
    seen = {start}
    queue = deque([start])
    while queue and len(seen) < limit:
        cell = queue.popleft()
        for neighbor in board.adjacent_cells(cell):
            if neighbor in board.barriers or neighbor in seen:
                continue
            seen.add(neighbor)
            queue.append(neighbor)
    return len(seen)


def barrier_threat(cell: Position, board: Board, belief: BeliefMap) -> float:
    """Estimate how exposed ``cell`` is to a plausible NEXT police barrier
    (Task 4C): police may only barrier its own cell or an orthogonal
    neighbor, so a cell close to the believed-likely police region, with
    few open neighbors of its own, is the most exposed -- a real,
    structural proxy since this peer never knows police's true position."""
    likely_cell, _ = top_k(belief, 1)[0]
    proximity = 1.0 / (1.0 + manhattan(cell, likely_cell))
    open_neighbors = sum(1 for c in board.adjacent_cells(cell) if not board.is_barrier(c))
    chokepoint = 1.0 / (1.0 + open_neighbors)
    return proximity * chokepoint


def score_move(
    *,
    origin: Position,
    destination: Position,
    belief: BeliefMap,
    projected_belief: BeliefMap,
    board: Board,
    visited: frozenset[Position],
    recent_directions: tuple,
    weights: EntropyEscapeWeights,
) -> float:
    """Higher is better for the THIEF: reward distance FROM the believed
    police location (opposite sign from the police's own pursuit utility),
    reward mobility/reachable-region size, penalize barrier-threat
    exposure, revisits, and overly-straight (predictable) trajectories."""
    origin_ed = expected_distance(belief, origin, manhattan)
    dest_ed = expected_distance(belief, destination, manhattan)
    score = weights.expected_distance * (dest_ed - origin_ed)

    projected_ed = expected_distance(projected_belief, destination, manhattan)
    score += weights.lookahead_distance * (projected_ed - origin_ed)

    score += weights.mobility * len(
        [c for c in board.adjacent_cells(destination) if not board.is_barrier(c)]
    )
    score += weights.reachable_region * (reachable_area(board, destination) / 30.0)

    score -= weights.barrier_threat_penalty * barrier_threat(destination, board, belief)

    if destination in visited:
        score -= weights.revisit_penalty

    if len(recent_directions) >= weights.straight_line_window and len(set(recent_directions)) == 1:
        score -= weights.straight_line_penalty

    return score


def capture_risk(destination: Position, belief: BeliefMap) -> float:
    """A bounded [0, 1]-ish proxy for how dangerous ``destination`` is,
    used to gate deceptive-hint selection (Task 4E): higher believed
    police probability mass near the destination = higher risk."""
    return belief.probability_at(destination)
