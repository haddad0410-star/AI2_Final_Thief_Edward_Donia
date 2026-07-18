"""Phase 8: template hints -- word limit, no coordinates, deterministic seeding,
truthful vs deceptive selection, Unicode robustness, and no LLM/network deps."""

from __future__ import annotations

import inspect
import random
import re

from thief_peer.domain.hints import HintIntent
from thief_peer.domain.positions import Direction
from thief_peer.strategy import hint_templates
from thief_peer.strategy.hint_templates import (
    DECEPTIVE_TEMPLATES,
    TRUTHFUL_TEMPLATES,
    TemplateHintProvider,
    region_for_direction,
)

COORD_PATTERN = re.compile(r"\(?\d+\s*,\s*\d+\)?")
ANY_DIGIT = re.compile(r"\d")


def _all_hints() -> list[str]:
    hints = []
    for seed in range(200):
        provider = TemplateHintProvider(rng=random.Random(seed))
        for intent in (HintIntent.TRUTH, HintIntent.LIE):
            for region in (None, "northern", "central"):
                hints.append(provider.generate(intent, region))
    return hints


def test_word_limit_enforced() -> None:
    for hint in _all_hints():
        assert len(hint.split()) <= 15


def test_no_coordinate_pairs_or_digits() -> None:
    for hint in _all_hints():
        assert COORD_PATTERN.search(hint) is None, hint
        assert ANY_DIGIT.search(hint) is None, hint


def test_at_least_six_templates_each() -> None:
    assert len(TRUTHFUL_TEMPLATES) >= 6
    assert len(DECEPTIVE_TEMPLATES) >= 6


def test_truthful_and_deceptive_pools_are_distinct() -> None:
    provider = TemplateHintProvider(rng=random.Random(0))
    truthful = {
        TemplateHintProvider(rng=random.Random(s)).generate(HintIntent.TRUTH, "northern")
        for s in range(50)
    }
    deceptive = {
        TemplateHintProvider(rng=random.Random(s)).generate(HintIntent.LIE, "northern")
        for s in range(50)
    }
    assert truthful and deceptive
    assert truthful.isdisjoint(deceptive)
    assert provider.generate(HintIntent.TRUTH, "central")  # smoke


def test_deterministic_in_test_mode() -> None:
    a = TemplateHintProvider(rng=random.Random(42)).generate(HintIntent.TRUTH)
    b = TemplateHintProvider(rng=random.Random(42)).generate(HintIntent.TRUTH)
    assert a == b


def test_region_for_direction_maps_to_words() -> None:
    assert region_for_direction(Direction.N) == "northern"
    assert region_for_direction(Direction.STAY) == "central"


def test_unicode_max_words_clamp() -> None:
    provider = TemplateHintProvider(max_words=3)
    clamped = provider._clamp_words("הגנב פונה מזרחה אל הרחוב הצפוני עכשיו")
    assert len(clamped.split()) == 3


def test_module_imports_no_network_or_llm_libraries() -> None:
    source = inspect.getsource(hint_templates)
    for banned in ("import requests", "import httpx", "import anthropic", "urllib", "socket"):
        assert banned not in source, f"hint module must not use {banned}"
