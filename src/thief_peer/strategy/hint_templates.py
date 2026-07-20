"""Offline template hint provider (Batch 2 Phase 8).

Produces short natural-language hints -- zero LLM tokens, no network, no imports
of any HTTP/LLM client. A hint is at most ``hint_max_words`` words (15 by
binding config), contains NO coordinates or numeric pairs, and may be truthful
or deceptive purely according to the ``intent`` flag the caller passes in (the
thief is book-permitted to lie in the hint text only; this module has no access
to physical/cryptographic fields). Deterministic under an injected RNG.

All template strings below are original to this project; the district/route
phrasing is illustrative, not copied verbatim from the assignment examples.
"""

from __future__ import annotations

import random

from thief_peer.domain.hint_region import REGIONS, region_for_direction
from thief_peer.domain.hints import HintIntent

__all__ = [
    "REGIONS",
    "DECEPTIVE_TEMPLATES",
    "TRUTHFUL_TEMPLATES",
    "TemplateHintProvider",
    "region_for_direction",
]

#: Hints that gesture toward the true intent ("I am heading roughly {region}").
TRUTHFUL_TEMPLATES = (
    "I am drifting toward the {region} districts now.",
    "The {region} routes look like my best way out.",
    "My path bends into the {region} quarter of the map.",
    "The {region} streets are calling me this turn.",
    "I lean toward the {region} avenues from here.",
    "Expect me somewhere along the {region} corridors.",
)

#: Hints meant to mislead (the declared intent is honestly 'lie').
DECEPTIVE_TEMPLATES = (
    "The {region} plazas feel far too exposed to risk.",
    "I would never waste a move on the {region} alleys.",
    "Forget the {region} boulevards; they lead nowhere useful.",
    "The {region} market district is the last place I'd go.",
    "Nothing draws me toward the {region} waterfront today.",
    "I am steering well clear of the {region} rooftops.",
)


class TemplateHintProvider:
    """Deterministic-given-seed offline hint renderer."""

    def __init__(self, rng: random.Random | None = None, max_words: int = 15) -> None:
        self._rng = rng or random.Random()
        self._max_words = max_words

    def generate(self, intent: HintIntent, region: str | None = None) -> str:
        """Render a hint consistent with ``intent``. ``region`` (a cardinal word)
        flavours the text; when omitted a region is chosen via the RNG."""
        pool = TRUTHFUL_TEMPLATES if intent is HintIntent.TRUTH else DECEPTIVE_TEMPLATES
        chosen_region = region if region in REGIONS else self._rng.choice(REGIONS)
        text = self._rng.choice(pool).format(region=chosen_region)
        return self._clamp_words(text)

    def generate_for_direction(self, intent: HintIntent, direction) -> str:
        """Derive the region word from ``direction``/``intent`` (true region
        when honest, a plausible wrong one when lying -- Batch 3.5 Task 5)
        using this provider's own RNG, then render."""
        from thief_peer.domain.hint_region import region_for_intent

        return self.generate(intent, region_for_intent(direction, intent, self._rng))

    def _clamp_words(self, text: str) -> str:
        words = text.split()
        if len(words) <= self._max_words:
            return text
        return " ".join(words[: self._max_words])
