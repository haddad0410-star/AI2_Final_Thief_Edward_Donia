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

    @classmethod
    def initial(cls, grid_size: int, sub_game_number: int, start: Position) -> SubGameState:
        """Fresh state at a sub-game start: thief at `start`, uniform belief."""
        return cls(
            grid_size=grid_size,
            sub_game_number=sub_game_number,
            position=start,
            board=Board(grid_size=grid_size),
            belief=uniform_prior(grid_size),
            own_scent=empty_scent_field(grid_size),
            machine=PeerStateMachine(),
            exchange=CommitRevealExchange(),
            visited={start},
        )

    def state_digest(self) -> str:
        """A compact, sealable representation of OWN state (never the opponent's).
        Includes own cell and visited-count -- enough to bind the record without
        leaking anything private about the opponent."""
        return f"pos={self.position.row},{self.position.col};visited={len(self.visited)}"
