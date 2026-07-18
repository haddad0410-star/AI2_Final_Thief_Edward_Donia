"""Dynamic strategy-class loader (Batch 2 Phase 7).

Loads a ``package.module:ClassName`` reference (Appendix F Table 22 style) from
the private ``game.toml`` -- never the shared/negotiated config. Raises a clear
error if the module or class cannot be resolved, rather than silently falling
back, so a misconfigured strategy is caught at startup.
"""

from __future__ import annotations

import importlib
import random
from typing import Any


class StrategyLoadError(Exception):
    """Raised when a configured strategy class cannot be imported/resolved."""


def load_strategy_class(reference: str) -> type:
    """Resolve a ``"pkg.module:ClassName"`` reference to the class object."""
    if ":" not in reference:
        raise StrategyLoadError(
            f"strategy reference must be 'package.module:ClassName', got {reference!r}"
        )
    module_name, _, class_name = reference.partition(":")
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise StrategyLoadError(f"cannot import strategy module {module_name!r}: {exc}") from exc
    try:
        return getattr(module, class_name)
    except AttributeError as exc:
        raise StrategyLoadError(
            f"class {class_name!r} not found in module {module_name!r}"
        ) from exc


def build_strategy(reference: str, rng: random.Random | None = None) -> Any:
    """Load and instantiate a strategy brain with an optional injected RNG."""
    brain_cls = load_strategy_class(reference)
    return brain_cls(rng=rng)
