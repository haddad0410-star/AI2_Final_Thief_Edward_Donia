"""Batch 3, Task 5: strategy profile / private-config validation --
import path, class interface, missing class, invalid weight, unknown key,
unsafe value."""

from __future__ import annotations

import random

import pytest

from thief_peer.shared.errors import ConfigError
from thief_peer.shared.private_config import PrivateGameConfig
from thief_peer.strategy.entropy_escape_config import weights_from_dict
from thief_peer.strategy.loader import StrategyLoadError, build_strategy

_BASE = {
    "game": {"group_name": "g", "group_id": "g", "members": [], "repos": {}},
    "network": {"my_port": 8902, "opponent_url": "http://127.0.0.1:8901/mcp"},
}


def test_missing_class_raises_strategy_load_error() -> None:
    with pytest.raises(StrategyLoadError):
        build_strategy("thief_peer.strategy.baseline_thief_brain:DoesNotExist")


def test_wrong_role_class_rejected() -> None:
    """A class with no decide(ctx) method must be rejected -- the practical
    interface/'wrong role' check for a duck-typed loader."""
    with pytest.raises(StrategyLoadError):
        build_strategy("thief_peer.domain.roles:Role")


def test_bad_import_path_format_rejected() -> None:
    with pytest.raises(StrategyLoadError):
        build_strategy("not_a_valid_reference")


def test_invalid_weight_value_rejected() -> None:
    with pytest.raises(ValueError, match="unknown"):
        weights_from_dict({"totally_bogus_weight": 1.0})


def test_unsafe_non_numeric_weight_value_rejected_at_config_load() -> None:
    data = {
        **_BASE,
        "strategy": {"profile": "experiment", "weights": {"expected_distance": "rm -rf /"}},
    }
    with pytest.raises(ConfigError, match="numeric"):
        PrivateGameConfig.from_dict(data)


def test_unknown_profile_name_rejected() -> None:
    data = {**_BASE, "strategy": {"profile": "not_a_real_profile"}}
    with pytest.raises(ConfigError, match="unknown strategy profile"):
        PrivateGameConfig.from_dict(data)


def test_baseline_profile_is_the_default() -> None:
    private = PrivateGameConfig.from_dict(_BASE)
    assert private.strategy.profile == "baseline"
    assert private.strategy.weights == {}


def test_advanced_profile_loads_with_default_weights() -> None:
    data = {
        **_BASE,
        "strategy": {
            "profile": "advanced",
            "thief_class": "thief_peer.strategy.entropy_escape_thief_brain:EntropyEscapeThiefBrain",
        },
    }
    private = PrivateGameConfig.from_dict(data)
    assert private.strategy.profile == "advanced"
    brain = build_strategy(private.strategy.thief_class, rng=random.Random(1))
    assert type(brain).__name__ == "EntropyEscapeThiefBrain"


def test_experiment_profile_applies_weight_overrides() -> None:
    data = {
        **_BASE,
        "strategy": {
            "profile": "experiment",
            "thief_class": "thief_peer.strategy.entropy_escape_thief_brain:EntropyEscapeThiefBrain",
            "weights": {"expected_distance": 3.5},
        },
    }
    private = PrivateGameConfig.from_dict(data)
    weights = weights_from_dict(private.strategy.weights)
    brain = build_strategy(private.strategy.thief_class, rng=random.Random(1), weights=weights)
    assert brain._weights.expected_distance == 3.5


def test_baseline_class_ignores_weights_argument_safely() -> None:
    """Passing weights to a class with no such constructor parameter must
    never raise -- BaselineThiefBrain is instantiated with just rng."""
    weights = weights_from_dict({"expected_distance": 9.0})
    brain = build_strategy(
        "thief_peer.strategy.baseline_thief_brain:BaselineThiefBrain",
        rng=random.Random(1),
        weights=weights,
    )
    assert type(brain).__name__ == "BaselineThiefBrain"
