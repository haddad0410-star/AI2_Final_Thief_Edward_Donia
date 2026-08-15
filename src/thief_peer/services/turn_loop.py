"""One turn of the thief sub-game, following the Phase 2 state machine and the
commit -> acknowledge -> reveal -> resolve sequence (Batch 2 Phase 9).

Every lifecycle change routes through the state machine; strategy code is given
no reference to it. Any technical failure (opponent malformed/unreachable,
deadline exceeded) becomes an explicit TECHNICAL_LOSS via the ERROR path, never a
hang. This module never reads the opponent's true position.
"""

from __future__ import annotations

import time

from thief_peer.domain.actions import MoveAction
from thief_peer.domain.captures import SubGameResult
from thief_peer.domain.deadline import DeadlineTracker
from thief_peer.domain.positions import Direction
from thief_peer.domain.rules import apply_move, legal_move_directions
from thief_peer.domain.scent import apply_turn
from thief_peer.domain.state_machine import EventKind, TransitionEvent
from thief_peer.infrastructure.mcp_client import PeerUnavailableError
from thief_peer.services import turn_gui_publish as gui
from thief_peer.services import turn_trace
from thief_peer.services.belief_update import update_belief
from thief_peer.services.capture_resolution import resolve_capture
from thief_peer.services.outcomes import TurnResult
from thief_peer.services.subgame_state import SubGameState
from thief_peer.services.turn_exchange import ExchangeError, deliver_commit_and_reveal
from thief_peer.services.turn_messages import commitment_message, reveal_message
from thief_peer.services.turn_prep import absorb_public_evidence, seal_turn
from thief_peer.strategy.decision import ThiefDecisionInput

_EV = EventKind


def _ev(kind: EventKind, detail: str = "") -> TransitionEvent:
    return TransitionEvent(kind=kind, detail=detail)


async def run_turn(state: SubGameState, deps) -> TurnResult:
    """Run a single turn; returns whether the sub-game ended and how."""
    try:
        return await _run_turn(state, deps)
    except (PeerUnavailableError, KeyError, ValueError, ExchangeError) as exc:
        progress = exc.progress if isinstance(exc, ExchangeError) else None
        state.machine.force_error(str(exc))
        gui.exchange_failed(state, deps.config_sha256, state.machine.state.value, progress)
        gui.result_for(
            state,
            "technical_loss",
            f"technical loss: {exc}",
            len(state.records),
            state.machine.state.value,
        )
        return TurnResult(True, SubGameResult.TECHNICAL_LOSS, f"technical loss: {exc}")


async def _run_turn(state: SubGameState, deps) -> TurnResult:
    state.machine.apply(_ev(_EV.BEGIN_TURN, f"step {state.step}"))
    rho = deps.config.pheromones.pheromone_decay
    belief_before = state.belief
    state.own_scent = apply_turn(state.own_scent, state.position, rho)
    state.belief, state.hint_trust = update_belief(
        state.belief, state.board, state.police_scent, state.hint_region, state.hint_trust
    )

    legal = legal_move_directions(state.position, state.board)
    deadline = DeadlineTracker(deps.response_timeout).start()
    ctx = ThiefDecisionInput(
        legal_directions=legal,
        position=state.position,
        visited=frozenset(state.visited),
        board=state.board,
        belief=state.belief,
        step=state.step,
        deadline=deadline,
    )
    position_before = state.position
    t0 = time.perf_counter()
    decision = deps.brain.decide(ctx)
    latency = time.perf_counter() - t0
    hint = deps.hint_provider.generate_for_direction(decision.intent, decision.direction)
    turn_trace.record_decide_turn(
        state=state, belief_before=belief_before, brain=deps.brain, decision=decision, hint=hint
    )
    destination_preview = apply_move(state.position, MoveAction(decision.direction), state.board)
    gui.decision(
        sub_game_number=state.sub_game_number,
        step=state.step,
        position_before=position_before,
        position_after=destination_preview,
        visited_count=len(state.visited),
        action=decision.direction.value,
        belief=state.belief,
        hint_text=hint,
        strategy_class=type(deps.brain).__module__ + "." + type(deps.brain).__qualname__,
        latency=latency,
    )

    record = seal_turn(state, decision.direction, decision.intent, hint, deps)
    state.exchange.commit(state.step, record.commit_hash)
    state.machine.apply(_ev(_EV.MOVE_DECIDED))

    state.machine.apply(_ev(_EV.COMMIT_SENT))
    was_confirming_prior_capture = state.pending_claim_response is True
    outgoing_reveal = reveal_message(record, deps.game_uid, deps.config_sha256)
    if deps.reveal_transform is not None:
        outgoing_reveal = deps.reveal_transform(outgoing_reveal)
    outcome = await deliver_commit_and_reveal(
        deps.gateway,
        commitment_message(record, deps.game_uid, deps.config_sha256),
        outgoing_reveal,
    )
    state.exchange.acknowledge(state.step)
    state.machine.apply(_ev(_EV.ACK_RECEIVED))
    state.exchange.reveal(state.step, record)
    state.machine.apply(_ev(_EV.REVEAL_SENT))
    state.records.append(record)
    reveal_ack = outcome.reveal_ack

    # If the reveal just sent above carried a True ``claim_response``, that
    # answer was already computed and pending from LAST turn (the
    # synchronous per-step exchange structurally cannot answer a same-step
    # claim -- both peers send their own reveal before receiving the
    # other's; see observation_pipeline_audit.md addendum, defect H (a
    # development-workspace artifact under the full project workspace's
    # integration_lab/evidence/batch3_5/, not included in this standalone
    # package). Having now
    # delivered it, this peer's own sub-game ends here -- there is no
    # further legal move for an already-captured thief to make.
    if was_confirming_prior_capture:
        state.machine.apply(_ev(_EV.SUB_GAME_ENDED, "captured"))
        gui.result_for(
            state,
            "capture",
            "captured (confirmed to opponent)",
            len(state.records),
            state.machine.state.value,
        )
        return TurnResult(True, SubGameResult.CAPTURE, "captured (confirmed to opponent)")

    return _resolve_and_advance(
        state, decision.direction, reveal_ack.get("opponent_turn", {}), deps
    )


def _resolve_and_advance(state: SubGameState, direction: Direction, opp: dict, deps) -> TurnResult:
    resolution = resolve_capture(
        state.position, opp.get("capture_claim"), opp.get("barrier_placed")
    )
    absorb_public_evidence(state, opp)
    turn_trace.record_turn_exchange(state=state, opp=opp)
    gui.exchange_ok(state, opp.get("hint", "") or "", deps.config_sha256, state.machine.state.value)
    if resolution.captured:
        state.pending_claim_response = True
    elif resolution.response is not None:
        state.pending_claim_response = resolution.response.caught
    else:
        state.pending_claim_response = None

    if resolution.captured:
        # The honest confirmation cannot be delivered until NEXT turn's
        # reveal (see ``_run_turn``'s ``was_confirming_prior_capture``
        # handling) -- an already-captured thief makes no further real
        # move; advance bookkeeping only, position frozen.
        state.machine.apply(_ev(_EV.TURN_VERIFIED))
        state.step += 1
        return TurnResult(False, None, "captured, confirmation pending")

    state.position = apply_move(state.position, MoveAction(direction), state.board)
    state.visited.add(state.position)
    if state.step + 1 >= deps.survival_threshold:
        state.machine.apply(_ev(_EV.SUB_GAME_ENDED, "survived"))
        gui.result_for(
            state,
            "survival",
            "reached survival threshold",
            len(state.records),
            state.machine.state.value,
        )
        return TurnResult(True, SubGameResult.SURVIVAL, "reached survival threshold")

    state.machine.apply(_ev(_EV.TURN_VERIFIED))
    state.step += 1
    return TurnResult(False, None, "turn complete")
