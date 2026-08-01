"""The mutual final-agreement rule (post-Batch-4B fix). Independent
implementation -- no import of the Police repository.

Per the book's rule, a disagreement between the two peers' declared totals
scores ZERO for both (never a silent average) -- represented here as an
explicit ``disputed_zeroed`` outcome.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FinalAgreement:
    """The end-of-series mutual-audit outcome and the totals it certifies."""

    agreed: bool
    status: str
    police_total: int
    thief_total: int


def resolve_final_agreement(
    our_police: int,
    our_thief: int,
    their_police: int | None,
    their_thief: int | None,
) -> FinalAgreement:
    """Certify agreed totals, or zero BOTH on any disagreement. ``their_*``
    is ``None`` when no opponent submission arrived -- our own totals stand
    as provisional/unverified, never silently promoted to agreed."""
    if their_police is None or their_thief is None:
        return FinalAgreement(False, "unverified_self_play", our_police, our_thief)
    if (our_police, our_thief) == (their_police, their_thief):
        return FinalAgreement(True, "agreed", our_police, our_thief)
    return FinalAgreement(False, "disputed_zeroed", 0, 0)
