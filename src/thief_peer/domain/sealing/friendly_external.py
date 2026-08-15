"""Isolated, opt-in commitment construction for the UNCOUNTED sharNamr
friendly only. NOT imported by any production match-running path
(game_runner.py, series_runtime.py, subgame_runtime.py, gateway.py) -- the
default/counted-match commitment scheme in domain/sealing/commit.py is
unchanged and unaffected by this module's existence.

sharNamr's documented construction: SHA256(canonical_json(payload) + "|" +
nonce), nonce appended as raw UTF-8 bytes after the canonical JSON, rather
than embedded as a payload field (contrast our own formula, matching the
book-cited H = SHA256(canonical_json(state, move, intent, nonce)),
Ch.5.3/App.E rule 17, where nonce IS a field inside the canonicalized
object).
"""

from __future__ import annotations

import hashlib
import json


def canonical_json_bytes_friendly_external(value: object) -> bytes:
    """Byte-identical to sharNamr's stated canonicalization:
    json.dumps(value, sort_keys=True, ensure_ascii=False,
    separators=(",", ":"), allow_nan=False), UTF-8 encoded."""
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def compute_commit_hash_friendly_external(payload: dict, nonce: str) -> str:
    """H = SHA256(canonical_json(payload) + b"|" + nonce.encode()). `payload`
    must NOT itself contain a `nonce` key (sharNamr's payload and nonce are
    disjoint inputs, unlike our own sealed payload)."""
    if "nonce" in payload:
        raise ValueError("friendly-external payload must not itself contain a 'nonce' key")
    body = canonical_json_bytes_friendly_external(payload)
    final_bytes = body + b"|" + nonce.encode("utf-8")
    return hashlib.sha256(final_bytes).hexdigest()


#: Fields our own gameplay logic never reads from an opponent's reveal
#: (verified: services/turn_prep.py::absorb_public_evidence only ever reads
#: scent_grid/hint/barrier_placed; services/turn_loop.py only additionally
#: reads capture_claim -- move/position are carried in a reveal purely for
#: the SENDER's own local audit trail, never consumed by the receiver).
#: Deferring them from the live reveal is therefore a pure data-minimization
#: change, not a functional one.
_POSITION_DEFERRED_DROP_FIELDS = frozenset({"move", "position"})


def position_deferred_reveal_dict(public_reveal_dict: dict) -> dict:
    """For the sharNamr friendly ONLY: a stricter reveal shape that also
    withholds `move`/`position` (on top of the `nonce`/`intent` our default
    `public_reveal_dict()` already withholds). Expects an already-public
    dict (i.e. the output of `payload.public_reveal_dict()`) as input --
    never re-derives from the full sealed payload, so it can't
    accidentally leak nonce/intent through a different code path. Our own
    local audit trail (the full sealed record on disk) is unaffected --
    move/position are always present there; only what's TRANSMITTED live
    changes."""
    if "nonce" in public_reveal_dict or "intent" in public_reveal_dict:
        raise ValueError(
            "position_deferred_reveal_dict expects an already-public reveal dict "
            "(no nonce/intent) -- pass payload.public_reveal_dict(), not to_canonical_dict()"
        )
    return {k: v for k, v in public_reveal_dict.items() if k not in _POSITION_DEFERRED_DROP_FIELDS}


def reveal_message_position_deferred(
    reveal_message: dict,
) -> dict:
    """Wraps an already-built default `reveal_message(...)` dict (from
    services/turn_messages.py) and strips move/position from its nested
    `reveal` body only -- envelope/message_type untouched. Friendly-only;
    never called by the default match-running path."""
    body = reveal_message.get("reveal", {})
    return {
        **reveal_message,
        "reveal": position_deferred_reveal_dict(body),
    }
