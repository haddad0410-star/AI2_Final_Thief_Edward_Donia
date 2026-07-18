"""Six-sub-game local series runtime (Batch 2, Phase 10).

Runs `num_games` sub-games (default 6 from the binding shared config -- the
separately-named smoke fixture's `num_games=1` is reachable only via an
explicit caller-supplied override, e.g. a CLI `--smoke` flag) against a live
opponent. ONE lifecycle state machine and ONE series-wide `game_uid` persist
across the whole series; every OTHER per-sub-game local structure (own true
position, scent history, belief map, board/barrier state, step counter,
commitment/audit store) is freshly reset each sub-game by constructing a
fresh `SubGameRuntime` (see `SubGameState.initial`). A technical loss (ERROR)
ends the series immediately -- ERROR only permits QUIT, so no further
sub-game can legally begin. Independent implementation: no import of the
Police repository's series runtime.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from thief_peer.domain.captures import SubGameResult
from thief_peer.domain.state_machine import EventKind, PeerState, PeerStateMachine, TransitionEvent
from thief_peer.services.outcomes import SubGameRunResult
from thief_peer.services.subgame_deps import SubGameDeps
from thief_peer.services.subgame_runtime import SubGameRuntime

_EV = EventKind


@dataclass(frozen=True, slots=True)
class SeriesSubGameRecord:
    """One completed sub-game's scored, audited summary."""

    sub_game_number: int
    result: SubGameResult
    police_score: int
    thief_score: int
    steps_taken: int
    audit_verified: bool


@dataclass(frozen=True, slots=True)
class SeriesResult:
    """The whole-series outcome: per-sub-game records + aggregated totals."""

    sub_games: tuple[SeriesSubGameRecord, ...]
    police_total: int
    thief_total: int
    terminated_reason: str
    final_state: PeerState
    run_results: tuple[SubGameRunResult, ...] = field(default_factory=tuple)


async def run_series(
    deps_factory: Callable[[int], SubGameDeps],
    *,
    num_games: int,
    max_turns: int | None = None,
    machine: PeerStateMachine | None = None,
) -> SeriesResult:
    """Run a full series and return its aggregated result.

    `deps_factory(index)` builds fresh `SubGameDeps` (0-based index) for each
    sub-game -- typically a fresh opponent-gateway connection per sub-game,
    with the SAME `game_uid`/`config_sha256` every time (series-wide
    identity stays consistent; only the per-game connection/transport is
    new).

    `machine`, if given, MUST start at INITIALIZING (a fresh machine) and is
    shared with this peer's own incoming-message server (Phase 6's
    TurnRouter validates incoming messages against the exact same lifecycle
    state this runtime is advancing) -- see `sdk/game_runner.py`. Defaults
    to a fresh, standalone machine for a caller that has no server of its
    own to share it with (e.g. a unit test).
    """
    machine = machine if machine is not None else PeerStateMachine()
    records: list[SeriesSubGameRecord] = []
    run_results: list[SubGameRunResult] = []
    reason = "completed"
    for index in range(num_games):
        deps = deps_factory(index)
        runtime = SubGameRuntime(deps, sub_game_number=index + 1, machine=machine)
        result = await runtime.run(max_turns=max_turns, bootstrap=(index == 0))
        run_results.append(result)
        records.append(
            SeriesSubGameRecord(
                sub_game_number=index + 1,
                result=result.result,
                police_score=result.police_score,
                thief_score=result.thief_score,
                steps_taken=result.steps_taken,
                audit_verified=result.audit.verified if result.audit is not None else False,
            )
        )
        if machine.state is PeerState.ERROR:
            reason = "technical_loss_ended_series"
            break
        _advance_after_sub_game(machine, is_last=(index == num_games - 1))
    police_total = sum(r.police_score for r in records)
    thief_total = sum(r.thief_score for r in records)
    return SeriesResult(
        tuple(records), police_total, thief_total, reason, machine.state, tuple(run_results)
    )


def _advance_after_sub_game(machine: PeerStateMachine, *, is_last: bool) -> None:
    """From AUDITING (reached by SubGameRuntime._finalize's own BEGIN_AUDIT
    call): the last sub-game closes the whole series; any earlier one
    returns to WAITING for the next sub-game's bootstrap-free start."""
    kind = _EV.SERIES_AUDIT_DONE if is_last else _EV.NEXT_SUB_GAME
    machine.apply(TransitionEvent(kind=kind))
