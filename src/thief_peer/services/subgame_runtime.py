"""SubGameRuntime: run one complete thief sub-game against a live opponent
(Batch 2 Phase 9).

Owns the per-sub-game turn loop, the closing self-audit, and score calculation.
All lifecycle changes route through the Phase 2 state machine; the strategy brain
is never handed that machine. Technical failures surface as an explicit
TECHNICAL_LOSS outcome, never a hang.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from datetime import UTC, datetime

from thief_peer.domain.captures import SubGameResult
from thief_peer.domain.positions import Position
from thief_peer.domain.scoring import score_sub_game
from thief_peer.domain.sealing import audit_sealed_records
from thief_peer.domain.state_machine import EventKind, PeerState, TransitionEvent
from thief_peer.services.gateway import OpponentGateway
from thief_peer.services.outcomes import SubGameRunResult
from thief_peer.services.subgame_state import SubGameState
from thief_peer.services.turn_loop import run_turn
from thief_peer.shared.config_models import SharedGameConfig

_LIFECYCLE_TO_WAITING = (
    EventKind.SERVER_STARTED,
    EventKind.BEGIN_NEGOTIATION,
    EventKind.TERMS_SIGNED,
    EventKind.SUB_GAME_START,
)


@dataclass
class SubGameDeps:
    """Everything one sub-game turn needs, gathered once."""

    config: SharedGameConfig
    brain: object
    hint_provider: object
    gateway: OpponentGateway
    game_uid: str
    config_sha256: str

    @property
    def response_timeout(self) -> float:
        return float(self.config.network_and_league.response_timeout_sec)

    @property
    def survival_threshold(self) -> int:
        return self.config.movement_and_barriers.survival_threshold

    def now_iso(self) -> str:
        return datetime.now(UTC).isoformat()


class SubGameRuntime:
    """Drives one sub-game to a typed outcome."""

    def __init__(self, deps: SubGameDeps, sub_game_number: int = 1) -> None:
        self._deps = deps
        grid = deps.config.board_and_agents.grid_size
        start = Position(*deps.config.board_and_agents.thief_start)
        self.state = SubGameState.initial(grid, sub_game_number, start)

    def _fast_forward_to_waiting(self) -> None:
        for kind in _LIFECYCLE_TO_WAITING:
            detail = "config_sha256" if kind is EventKind.TERMS_SIGNED else ""
            self.state.machine.apply(TransitionEvent(kind=kind, detail=detail))

    async def run(self, max_turns: int | None = None) -> SubGameRunResult:
        """Run turns until a typed outcome; then self-audit and score.

        Every exit leaves the state machine in a legal state before this
        coroutine returns or raises:

        - Capture / survival: the turn loop itself drives VERIFYING ->
          SUB_GAME_OVER via ``SUB_GAME_ENDED``, so ``_finalize`` may legally
          run ``BEGIN_AUDIT``.
        - A protocol error (opponent malformed/unreachable): ``run_turn``
          already forces ERROR before returning, so ``_finalize`` correctly
          skips the audit.
        - ``max_turns`` smaller than what the configured
          ``survival_threshold`` needs (only reachable via an explicit
          caller-supplied cap -- the default cap, ``survival_threshold + 1``,
          can never fall through here, since the turn loop's own survival
          check always fires ``SUB_GAME_ENDED`` at or before that point):
          the ``for`` loop exhausts without ``break``, and :meth:`abort`
          forces ERROR and reports an explicit TECHNICAL_LOSS -- never a
          silently-claimed completed game.
        - External cancellation (e.g. a deadline/watchdog abort while
          WAITING, THINKING, or mid-turn): caught, recorded via
          :meth:`abort` for a consistent, inspectable final state, then
          re-raised -- cancellation is never silently swallowed.
        """
        self._fast_forward_to_waiting()
        cap = max_turns if max_turns is not None else self._deps.survival_threshold + 1
        try:
            for _ in range(cap):
                turn = await run_turn(self.state, self._deps)
                if turn.ended:
                    return self._finalize(turn.outcome, turn.reason)
        except asyncio.CancelledError:
            self.abort("cancelled")
            raise
        return self.abort("turn cap exhausted before a natural sub-game outcome")

    def abort(self, reason: str) -> SubGameRunResult:
        """Force this sub-game to a legal TECHNICAL_LOSS exit from wherever
        it currently is (WAITING, mid-turn, or already ERROR) and finalize
        it. Never leaves the state machine mid-transition, and -- because
        ``_finalize`` only audits a peer that is NOT in ERROR -- never
        claims a completed, verified audit for a game that did not reach a
        real terminal outcome.
        """
        if self.state.machine.state is not PeerState.ERROR:
            self.state.machine.force_error(reason)
        return self._finalize(SubGameResult.TECHNICAL_LOSS, reason)

    def _finalize(self, result: SubGameResult, reason: str) -> SubGameRunResult:
        records = tuple(self.state.records)
        audit = None
        if self.state.machine.state is not PeerState.ERROR:
            audit = audit_sealed_records(records)
            self.state.machine.apply(TransitionEvent(kind=EventKind.BEGIN_AUDIT))
            if not audit.verified:
                result, reason = SubGameResult.TECHNICAL_LOSS, audit.reason
        police, thief = score_sub_game(result, self._deps.config.scoring)
        return SubGameRunResult(
            result=result,
            steps_taken=len(records),
            reason=reason,
            records=records,
            audit=audit,
            police_score=police,
            thief_score=thief,
        )


def make_deps(
    config: SharedGameConfig,
    gateway: OpponentGateway,
    game_uid: str,
    config_sha256: str,
    *,
    brain: object | None = None,
    hint_provider: object | None = None,
    seed: int = 0,
) -> SubGameDeps:
    """Assemble SubGameDeps with the baseline brain + template hints by default."""
    from thief_peer.strategy.baseline_thief_brain import BaselineThiefBrain
    from thief_peer.strategy.hint_templates import TemplateHintProvider

    rng = random.Random(seed)
    return SubGameDeps(
        config=config,
        brain=brain or BaselineThiefBrain(rng=rng),
        hint_provider=hint_provider or TemplateHintProvider(rng=random.Random(seed + 1)),
        gateway=gateway,
        game_uid=game_uid,
        config_sha256=config_sha256,
    )
