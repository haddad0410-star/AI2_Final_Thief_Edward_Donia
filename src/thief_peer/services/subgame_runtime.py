"""SubGameRuntime: run one complete thief sub-game against a live opponent
(Batch 2 Phase 9).

Owns the per-sub-game turn loop, the closing self-audit, and score calculation.
All lifecycle changes route through the Phase 2 state machine; the strategy brain
is never handed that machine. Technical failures surface as an explicit
TECHNICAL_LOSS outcome, never a hang.
"""

from __future__ import annotations

import asyncio

from thief_peer.domain.captures import SubGameResult
from thief_peer.domain.positions import Position
from thief_peer.domain.scoring import score_sub_game
from thief_peer.domain.sealing import audit_sealed_records
from thief_peer.domain.state_machine import EventKind, PeerState, PeerStateMachine, TransitionEvent
from thief_peer.services.outcomes import SubGameRunResult
from thief_peer.services.subgame_deps import SubGameDeps, make_deps  # noqa: F401  (re-exported)
from thief_peer.services.subgame_state import SubGameState
from thief_peer.services.turn_loop import run_turn

_LIFECYCLE_TO_WAITING = (
    EventKind.SERVER_STARTED,
    EventKind.BEGIN_NEGOTIATION,
    EventKind.TERMS_SIGNED,
    EventKind.SUB_GAME_START,
)


class SubGameRuntime:
    """Drives one sub-game to a typed outcome."""

    def __init__(
        self,
        deps: SubGameDeps,
        sub_game_number: int = 1,
        *,
        machine: PeerStateMachine | None = None,
    ) -> None:
        """`machine`, if given, is shared across a whole series (Phase 10)
        instead of a fresh one starting at INITIALIZING -- see
        `SubGameState.initial`."""
        self._deps = deps
        grid = deps.config.board_and_agents.grid_size
        start = Position(*deps.config.board_and_agents.thief_start)
        self.state = SubGameState.initial(grid, sub_game_number, start, machine=machine)

    def _fast_forward_to_waiting(self) -> None:
        for kind in _LIFECYCLE_TO_WAITING:
            detail = "config_sha256" if kind is EventKind.TERMS_SIGNED else ""
            self.state.machine.apply(TransitionEvent(kind=kind, detail=detail))

    async def run(
        self, max_turns: int | None = None, *, bootstrap: bool = True
    ) -> SubGameRunResult:
        """Run turns until a typed outcome; then self-audit and score.

        `bootstrap=False` skips the SERVER_STARTED..SUB_GAME_START lifecycle
        fast-forward -- for sub-game 2+ of a series (Phase 10), the shared
        machine already sits at WAITING (reached via the *previous*
        sub-game's AUDITING -> NEXT_SUB_GAME transition), and replaying
        SERVER_STARTED from there would be an illegal transition. Standalone
        callers (the default) always start a fresh machine at INITIALIZING
        and need the full fast-forward, unchanged from before.

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
        if bootstrap:
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
