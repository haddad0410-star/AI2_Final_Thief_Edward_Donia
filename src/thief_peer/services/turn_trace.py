"""Optional local-only diagnostic trace hook (Batch 3.5, Task 3/11).

Active only when the ``THIEF_TRACE_FILE`` environment variable is set. Never
sent over the wire, never given to the strategy, never affects gameplay --
purely an append-only JSONL diagnostic log of this peer's OWN turn-local
values (never the opponent's true position), used to prove or disprove
observation-pipeline defects. See
``integration_lab/evidence/batch3_5/observation_pipeline_audit.md``.
"""

from __future__ import annotations

import json
import os
from typing import Any

from thief_peer.domain.belief_model import BeliefMap, entropy, top_k
from thief_peer.domain.scent import ScentField


def enabled() -> bool:
    return bool(os.environ.get("THIEF_TRACE_FILE"))


def belief_summary(belief: BeliefMap, k: int = 5) -> dict[str, Any]:
    return {
        "entropy": entropy(belief),
        "top_k": [[pos.row, pos.col, round(prob, 8)] for pos, prob in top_k(belief, k)],
    }


def scent_summary(scent: ScentField) -> dict[str, Any]:
    flat = [v for row in scent.grid for v in row]
    return {
        "dims": [scent.grid_size, scent.grid_size],
        "sum": round(sum(flat), 8),
        "min": round(min(flat), 8) if flat else None,
        "max": round(max(flat), 8) if flat else None,
    }


def record(event: dict[str, Any]) -> None:
    path = os.environ.get("THIEF_TRACE_FILE")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, default=str) + "\n")


def record_decide_turn(*, state, belief_before: BeliefMap, brain, decision, hint: str) -> None:
    if not enabled():
        return
    record(
        {
            "event": "decide_turn",
            "step": state.step,
            "sub_game_number": state.sub_game_number,
            "belief_before": belief_summary(belief_before),
            "belief_after_advance": belief_summary(state.belief),
            "received_police_scent": (
                scent_summary(state.police_scent) if state.police_scent is not None else None
            ),
            "hint_trust": state.hint_trust,
            "strategy_class": type(brain).__module__ + "." + type(brain).__qualname__,
            "action_selected": decision.direction.value,
            "outgoing_hint": hint,
            "outgoing_hint_intent": decision.intent.value,
            "local_emitted_scent": scent_summary(state.own_scent),
        }
    )


def record_turn_exchange(*, state, opp: dict) -> None:
    if not enabled():
        return
    record(
        {
            "event": "turn_exchange",
            "step": state.step,
            "sub_game_number": state.sub_game_number,
            "received_message_type": "reveal",
            "received_reveal_keys": sorted(opp.keys()),
            "received_police_scent_after_absorb": (
                scent_summary(state.police_scent) if state.police_scent is not None else None
            ),
            "received_hint": opp.get("hint"),
            "hint_region_decoded": state.hint_region is not None,
            "belief_after_absorb": belief_summary(state.belief),
        }
    )
