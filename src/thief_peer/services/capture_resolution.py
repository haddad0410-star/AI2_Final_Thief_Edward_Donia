"""Publicly-verifiable capture resolution for the thief (Batch 2 Phase 9).

The thief answers a police capture claim HONESTLY (a false answer is
cryptographically detectable at audit) and detects a barrier placed on its own
current cell (Appendix E rule 46). It never fabricates a claim of its own.
"""

from __future__ import annotations

from dataclasses import dataclass

from thief_peer.domain.captures import CaptureResponse
from thief_peer.domain.positions import Position
from thief_peer.domain.rules import is_barrier_on_thief_capture, is_ordinary_capture


@dataclass(frozen=True, slots=True)
class CaptureResolution:
    """The outcome of resolving one turn's public capture evidence."""

    captured: bool
    response: CaptureResponse | None
    reason: str


def resolve_capture(
    own_position: Position,
    claimed_cell: tuple[int, int] | None,
    barrier_cell: tuple[int, int] | None,
) -> CaptureResolution:
    """Resolve a police capture claim and/or a barrier declaration honestly."""
    if barrier_cell is not None:
        barrier_pos = Position(barrier_cell[0], barrier_cell[1])
        if is_barrier_on_thief_capture(barrier_pos, own_position):
            return CaptureResolution(True, None, "barrier placed on thief cell")

    if claimed_cell is not None:
        claimed_pos = Position(claimed_cell[0], claimed_cell[1])
        caught = is_ordinary_capture(own_position, claimed_pos)
        response = CaptureResponse(claimed_position=claimed_pos, caught=caught)
        reason = "capture claim correct" if caught else "capture claim wrong (honest deny)"
        return CaptureResolution(caught, response, reason)

    return CaptureResolution(False, None, "no capture evidence this turn")
