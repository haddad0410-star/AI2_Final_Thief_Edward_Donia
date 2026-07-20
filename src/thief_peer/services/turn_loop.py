"""One turn of the thief sub-game, following the Phase 2 state machine and the
commit -> acknowledge -> reveal -> resolve sequence (Batch 2 Phase 9).

Every lifecycle change routes through the state machine; strategy code is given
no reference to it. Any technical failure (opponent malformed/unreachable,
deadline exceeded) becomes an explicit TECHNICAL_LOSS via the ERROR path, never a
hang. This module never reads the opponent's true position.
"""

from __future__ import annotations

from thief_peer.domain.actions import MoveAction
from thief_peer.domain.captures import SubGameResult
from thief_peer.domain.deadline import DeadlineTracker
from thief_peer.domain.hints import HintIntent
from thief_peer.domain.positions import Direction
from thief_peer.domain.rules import apply_move, legal_move_directions
from thief_peer.domain.scent import ScentField, apply_turn
from thief_peer.domain.sealing import SealedTurnPayload, new_nonce, seal
from thief_peer.domain.state_machine import EventKind, TransitionEvent
from thief_peer.infrastructure.mcp_client import PeerUnavailableError
from thief_peer.services import turn_trace
from thief_peer.services.belief_update import update_belief
from thief_peer.services.capture_resolution import resolve_capture
from thief_peer.services.outcomes import TurnResult
from thief_peer.services.subgame_state import SubGameState
from thief_peer.services.turn_messages import commitment_message, reveal_message
from thief_peer.strategy.decision import ThiefDecisionInput

_EV = EventKind


def _ev(kind: EventKind, detail: str = "") -> TransitionEvent:
    return TransitionEvent(kind=kind, detail=detail)


async def run_turn(state: SubGameState, deps) -> TurnResult:
    """Run a single turn; returns whether the sub-game ended and how."""
    try:
        return await _run_turn(state, deps)
    except (PeerUnavailableError, KeyError, ValueError) as exc:
        state.machine.force_error(str(exc))
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
    decision = deps.brain.decide(ctx)
    hint = deps.hint_provider.generate_for_direction(decision.intent, decision.direction)
    turn_trace.record_decide_turn(
        state=state, belief_before=belief_before, brain=deps.brain, decision=decision, hint=hint
    )

    record = _seal_turn(state, decision.direction, decision.intent, hint, deps)
    state.exchange.commit(state.step, record.commit_hash)
    state.machine.apply(_ev(_EV.MOVE_DECIDED))

    state.machine.apply(_ev(_EV.COMMIT_SENT))
    ack = await deps.gateway.deliver_turn(
        commitment_message(record, deps.game_uid, deps.config_sha256)
    )
    if not ack.get("ok"):
        raise ValueError(f"commitment rejected: {ack}")
    state.exchange.acknowledge(state.step)
    state.machine.apply(_ev(_EV.ACK_RECEIVED))

    was_confirming_prior_capture = state.pending_claim_response is True

    reveal_ack = await deps.gateway.deliver_turn(
        reveal_message(record, deps.game_uid, deps.config_sha256)
    )
    if not reveal_ack.get("ok"):
        raise ValueError(f"reveal rejected: {reveal_ack}")
    state.exchange.reveal(state.step, record)
    state.machine.apply(_ev(_EV.REVEAL_SENT))
    state.records.append(record)

    # If the reveal just sent above carried a True ``claim_response``, that
    # answer was already computed and pending from LAST turn (the
    # synchronous per-step exchange structurally cannot answer a same-step
    # claim -- both peers send their own reveal before receiving the
    # other's; see integration_lab/evidence/batch3_5/
    # observation_pipeline_audit.md addendum, defect H). Having now
    # delivered it, this peer's own sub-game ends here -- there is no
    # further legal move for an already-captured thief to make.
    if was_confirming_prior_capture:
        state.machine.apply(_ev(_EV.SUB_GAME_ENDED, "captured"))
        return TurnResult(True, SubGameResult.CAPTURE, "captured (confirmed to opponent)")

    return _resolve_and_advance(
        state, decision.direction, reveal_ack.get("opponent_turn", {}), deps
    )


def _seal_turn(state: SubGameState, direction: Direction, intent: HintIntent, hint: str, deps):
    payload = SealedTurnPayload(
        step=state.step,
        role="thief",
        sub_game_number=state.sub_game_number,
        state=state.state_digest(),
        move=direction.value,
        intent=intent.value,
        hint=hint,
        scent_digest=_scent_digest(state.own_scent),
        scent_grid=state.own_scent.grid,
        claim_response=state.pending_claim_response,
        timestamp=deps.now_iso(),
        nonce=new_nonce(),
        config_sha256=deps.config_sha256,
    )
    return seal(payload)


def _scent_digest(scent: ScentField) -> str:
    from thief_peer.shared.canonical_json import canonical_sha256_hex

    return canonical_sha256_hex([list(row) for row in scent.grid])


def _resolve_and_advance(state: SubGameState, direction: Direction, opp: dict, deps) -> TurnResult:
    resolution = resolve_capture(
        state.position, opp.get("capture_claim"), opp.get("barrier_placed")
    )
    _absorb_public_evidence(state, opp)
    turn_trace.record_turn_exchange(state=state, opp=opp)
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
        return TurnResult(True, SubGameResult.SURVIVAL, "reached survival threshold")

    state.machine.apply(_ev(_EV.TURN_VERIFIED))
    state.step += 1
    return TurnResult(False, None, "turn complete")


def _absorb_public_evidence(state: SubGameState, opp: dict) -> None:
    """Fold the opponent's public reveal into local state: police's real
    scent grid (Batch 3.5 Task 4 -- previously read a ``police_scent`` key
    that does not exist in police's actual reveal dict, which only carries
    ``scent_grid``; see observation_pipeline_audit.md defect B2), and the
    hint's decoded region (Task 5 -- previously never parsed at all)."""
    from thief_peer.domain.hint_region import parse_region_from_hint, region_cells
    from thief_peer.domain.scent_validation import validate_scent_grid

    scent_grid = opp.get("scent_grid")
    if validate_scent_grid(scent_grid, state.grid_size) is None:
        rows = tuple(tuple(float(v) for v in row) for row in scent_grid)
        state.police_scent = ScentField(grid_size=state.grid_size, grid=rows)
    else:
        state.police_scent = None
    hint_text = opp.get("hint")
    region_word = parse_region_from_hint(hint_text) if hint_text else None
    state.hint_region = region_cells(region_word, state.grid_size) if region_word else None
    barrier = opp.get("barrier_placed")
    if barrier is not None:
        from thief_peer.domain.positions import Position

        state.board = state.board.with_barrier(Position(barrier[0], barrier[1]))
