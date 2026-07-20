"""Configurable utility weights for :class:`EntropyEscapeThiefBrain`
(Batch 3, Task 4G). A plain, private, documented dataclass -- never
hardcoded scattered through the decision logic, never part of the signed
shared ``game.json`` (Batch 3 rule 12).
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class EntropyEscapeWeights:
    """Utility-function component weights; see docs/STRATEGY.md for the
    full documented formula each one feeds into."""

    #: weight on expected-distance increase away from believed police location
    expected_distance: float = 1.0
    #: weight on projected post-lookahead expected distance (evasion signal)
    lookahead_distance: float = 0.8
    #: weight on immediate legal-move mobility at the candidate cell
    mobility: float = 0.5
    #: weight on wider reachable-region size at the candidate cell
    reachable_region: float = 0.4
    #: penalty for a candidate cell near a predicted police barrier threat
    barrier_threat_penalty: float = 1.2
    #: penalty per prior visit to the candidate cell (predictability control)
    revisit_penalty: float = 0.2
    #: penalty for repeating the same direction 3+ turns in a row
    straight_line_penalty: float = 0.3
    #: bounded lookahead depth (belief transition steps), 2-4 per Task 4F
    lookahead_depth: int = 2
    #: capture-risk score above which a deceptive hint is selected (Task 4E)
    deception_risk_threshold: float = 0.35
    #: how many consecutive same-direction moves before the straight-line
    #: penalty applies
    straight_line_window: int = 3

    def with_overrides(self, **overrides: float) -> EntropyEscapeWeights:
        """Return a copy with the given fields overridden -- used by the
        tuning harness (Task 8) to try bounded candidate configurations
        without ever mutating a shared instance."""
        return replace(self, **overrides)


DEFAULT_WEIGHTS = EntropyEscapeWeights()


def weights_from_dict(data: dict) -> EntropyEscapeWeights:
    """Build weights from a private-config dict; unknown keys are rejected
    (a mistyped weight name must never be silently ignored)."""
    known = set(EntropyEscapeWeights.__dataclass_fields__)
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"unknown EntropyEscapeWeights key(s): {sorted(unknown)}")
    return EntropyEscapeWeights(**data)
