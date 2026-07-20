"""SubGameState: the thief's own mutable local knowledge for one sub-game.

Owns ONLY this peer's truth plus legally-public info: own position/visited,
the board (public barriers received/echoed only -- the thief never places them),
its own scent field, its belief about the police, its sealed records, and its
audit/exchange state. There is deliberately NO opponent-true-position field
(enforced by tests/security/test_runtime_isolation.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from thief_peer.domain.belief_model import BeliefMap
from thief_peer.domain.belief_updates import uniform_prior
from thief_peer.domain.board import Board
from thief_peer.domain.positions import Position
from thief_peer.domain.scent import ScentField, empty_scent_field
from thief_peer.domain.sealing import CommitRevealExchange, SealedRecord
from thief_peer.domain.state_machine import PeerStateMachine


@dataclass
class SubGameState:
    """Mutable per-sub-game local state for the thief peer."""

    grid_size: int
    sub_game_number: int
    position: Position
    board: Board
    belief: BeliefMap
    own_scent: ScentField
    machine: PeerStateMachine
    exchange: CommitRevealExchange
    visited: set[Position] = field(default_factory=set)
    records: list[SealedRecord] = field(default_factory=list)
    step: int = 0
    #: Last PUBLIC police scent grid received (never a true position).
    police_scent: ScentField | None = None
    #: The region a just-received hint decodes to, or None if no hint
    #: evidence is available this turn (Batch 3.5 Task 5).
    hint_region: frozenset[Position] | None = None
    #: Bounded [0,1] consistency-based trust in hint evidence, carried
    #: across turns within one sub-game; never derived from the sealed
    #: intent field.
    hint_trust: float = 0.5
    #: The honest answer to the police's MOST RECENTLY received capture
    #: claim, not yet delivered -- included in the NEXT outgoing reveal
    #: (Batch 3.5 Task 4/9: the synchronous per-step commit/reveal exchange
    #: structurally cannot answer a same-step claim, since both peers send
    #: their own reveal before receiving the other's; see
    #: integration_lab/evidence/batch3_5/observation_pipeline_audit.md
    #: addendum, defect H). ``None`` means no claim evidence arrived yet.
    pending_claim_response: bool | None = None

    @classmethod
    def initial(
        cls,
        grid_size: int,
        sub_game_number: int,
        start: Position,
        machine: PeerStateMachine | None = None,
    ) -> SubGameState:
        """Fresh LOCAL state at a sub-game start: thief at `start`, uniform
        belief, empty scent/board/records/exchange/step counter.

        `machine` lets a caller running a multi-sub-game series (Phase 10)
        share ONE lifecycle state machine across sub-games -- only the
        per-sub-game local knowledge resets, never the series-wide
        lifecycle position. Defaults to a fresh machine (starting at
        INITIALIZING) for a standalone single sub-game, unchanged from
        before.
        """
        return cls(
            grid_size=grid_size,
            sub_game_number=sub_game_number,
            position=start,
            board=Board(grid_size=grid_size),
            belief=uniform_prior(grid_size),
            own_scent=empty_scent_field(grid_size),
            machine=machine if machine is not None else PeerStateMachine(),
            exchange=CommitRevealExchange(),
            visited={start},
        )

    def state_digest(self) -> str:
        """A compact, sealable representation of OWN state (never the opponent's).
        Includes own cell and visited-count -- enough to bind the record without
        leaking anything private about the opponent."""
        return f"pos={self.position.row},{self.position.col};visited={len(self.visited)}"
