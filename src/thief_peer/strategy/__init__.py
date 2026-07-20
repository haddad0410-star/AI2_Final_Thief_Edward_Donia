"""Move-selection strategies: BaselineThiefBrain (Batch 2) and
EntropyEscapeThiefBrain (Batch 3, original advanced strategy).

See docs/ARCHITECTURE.md for this package's responsibility. Submodules are
imported directly by callers (``thief_peer.strategy.loader.build_strategy``
resolves a private-config ``package.module:ClassName`` reference), so this
file re-exports the two brains and their shared value types for convenience
only.
"""

from __future__ import annotations

from thief_peer.strategy.baseline_thief_brain import BaselineThiefBrain
from thief_peer.strategy.decision import Decision, ThiefDecisionInput
from thief_peer.strategy.entropy_escape_config import DEFAULT_WEIGHTS, EntropyEscapeWeights
from thief_peer.strategy.entropy_escape_thief_brain import EntropyEscapeThiefBrain
from thief_peer.strategy.loader import StrategyLoadError, build_strategy

__all__ = [
    "DEFAULT_WEIGHTS",
    "BaselineThiefBrain",
    "Decision",
    "EntropyEscapeThiefBrain",
    "EntropyEscapeWeights",
    "StrategyLoadError",
    "ThiefDecisionInput",
    "build_strategy",
]
