"""Dynamic strategy-class loader (Batch 2 Phase 7).

Loads a ``package.module:ClassName`` reference (Appendix F Table 22 style) from
the private ``game.toml`` -- never the shared/negotiated config. Raises a clear
error if the module or class cannot be resolved, rather than silently falling
back, so a misconfigured strategy is caught at startup.
"""

from __future__ import annotations

import importlib
import inspect
import random
from typing import Any


class StrategyLoadError(Exception):
    """Raised when a configured strategy class cannot be imported/resolved."""


def load_strategy_class(reference: str) -> type:
    """Resolve a ``"pkg.module:ClassName"`` reference to the class object,
    validating it exposes the required ``decide(ctx)`` interface (Thief
    brains are duck-typed, not built on a shared ABC -- this is the
    practical equivalent of Police's ``issubclass`` check, Batch 3 Task 5)."""
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
        cls = getattr(module, class_name)
    except AttributeError as exc:
        raise StrategyLoadError(
            f"class {class_name!r} not found in module {module_name!r}"
        ) from exc
    if not (isinstance(cls, type) and callable(getattr(cls, "decide", None))):
        raise StrategyLoadError(f"{reference!r} does not expose a decide(ctx) method")
    return cls


def build_strategy(
    reference: str, rng: random.Random | None = None, weights: object | None = None
) -> Any:
    """Load and instantiate a strategy brain with an optional injected RNG.

    ``weights`` (Batch 3) is passed through only if the resolved class's
    constructor actually accepts a ``weights`` parameter (e.g.
    ``EntropyEscapeThiefBrain``); a class with no such parameter (e.g.
    ``BaselineThiefBrain``) is instantiated with just ``rng``, unaffected.
    """
    brain_cls = load_strategy_class(reference)
    if weights is not None and "weights" in inspect.signature(brain_cls.__init__).parameters:
        return brain_cls(rng=rng, weights=weights)
    return brain_cls(rng=rng)
