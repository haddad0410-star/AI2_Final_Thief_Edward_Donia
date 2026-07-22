"""Batch 3.5 Task 4/5: scent + hint transport/trust repair coverage (thief side)."""

from __future__ import annotations

import json

from thief_peer.domain.board import Board
from thief_peer.domain.hint_region import parse_region_from_hint, region_cells
from thief_peer.domain.hints import HintIntent
from thief_peer.domain.positions import Position
from thief_peer.domain.scent import apply_turn, empty_scent_field
from thief_peer.domain.scent_validation import validate_scent_grid
from thief_peer.domain.sealing import SealedTurnPayload
from thief_peer.domain.sealing.commit import commit_hash as compute_commit_hash
from thief_peer.services.belief_update import update_belief
from thief_peer.shared.canonical_json import canonical_sha256_hex
from thief_peer.strategy.hint_templates import TemplateHintProvider

GRID = 7


def _payload(
    scent_grid, intent="truth", hint="the northern avenues feel exposed"
) -> SealedTurnPayload:
    return SealedTurnPayload(
        step=0,
        role="thief",
        sub_game_number=1,
        position=(0, 0),
        move="N",
        intent=intent,
        hint=hint,
        scent_digest=canonical_sha256_hex([list(row) for row in scent_grid]),
        scent_grid=scent_grid,
        timestamp="2026-07-18T00:00:00+00:00",
        nonce="a" * 64,
        config_sha256="b" * 64,
    )


def test_nonzero_scent_crosses_real_serialization() -> None:
    field = apply_turn(empty_scent_field(GRID), Position(4, 4), 0.10)
    wire = json.loads(json.dumps(_payload(field.grid).public_reveal_dict()))
    assert wire["scent_grid"][4][4] == field.grid[4][4] > 0.0


def test_intent_not_revealed_early() -> None:
    reveal = _payload(empty_scent_field(GRID).grid, intent="lie").public_reveal_dict()
    assert "intent" not in reveal
    assert "nonce" not in reveal


def test_commitment_covers_scent() -> None:
    a = apply_turn(empty_scent_field(GRID), Position(1, 1), 0.10)
    b = apply_turn(empty_scent_field(GRID), Position(6, 6), 0.10)
    assert compute_commit_hash(_payload(a.grid)) != compute_commit_hash(_payload(b.grid))


def test_malformed_scent_rejected() -> None:
    assert validate_scent_grid(((0.1, 0.2),), GRID) == "bad_dimensions"
    assert validate_scent_grid(None, GRID) == "missing"
    grid = [[-1.0] * GRID for _ in range(GRID)]
    assert validate_scent_grid(grid, GRID) == "negative"


def test_valid_scent_accepted() -> None:
    field = apply_turn(empty_scent_field(GRID), Position(2, 2), 0.10)
    assert validate_scent_grid(field.grid, GRID) is None


def test_receiving_scent_changes_belief_via_update_belief() -> None:
    from thief_peer.domain.belief_updates import uniform_prior

    board = Board(grid_size=GRID)
    belief = uniform_prior(GRID)
    field = apply_turn(empty_scent_field(GRID), Position(5, 5), 0.10)
    after, trust = update_belief(belief, board, field, None, 0.5)
    assert after.grid[5][5] != belief.grid[5][5]
    assert trust == 0.5  # no hint evidence this turn -> trust unchanged


def test_hint_region_boosts_belief() -> None:
    from thief_peer.domain.belief_updates import uniform_prior

    board = Board(grid_size=GRID)
    belief = uniform_prior(GRID)
    region = region_cells("northern", GRID)
    before_mass = sum(belief.grid[p.row][p.col] for p in region)
    after, _trust = update_belief(belief, board, None, region, 0.5)
    after_mass = sum(after.grid[p.row][p.col] for p in region)
    assert after_mass > before_mass


def test_impossible_cells_remain_zero_with_hint() -> None:
    from thief_peer.domain.belief_updates import uniform_prior

    board = Board(grid_size=GRID)
    for r in range(GRID):
        board = board.with_barrier(Position(r, 0))
    belief = uniform_prior(GRID, board.barriers)
    region = region_cells("western", GRID)
    after, _trust = update_belief(belief, board, None, region, 0.5)
    for r in range(GRID):
        assert after.grid[r][0] == 0.0


def test_generate_for_direction_true_region_matches_direction() -> None:
    import random

    from thief_peer.domain.positions import Direction

    provider = TemplateHintProvider(rng=random.Random(0))
    text = provider.generate_for_direction(HintIntent.TRUTH, Direction.N)
    assert parse_region_from_hint(text) == "northern"


def test_generate_for_direction_lie_uses_wrong_region() -> None:
    import random

    from thief_peer.domain.positions import Direction

    provider = TemplateHintProvider(rng=random.Random(1))
    for _ in range(20):
        text = provider.generate_for_direction(HintIntent.LIE, Direction.N)
        assert parse_region_from_hint(text) != "northern"


def test_no_true_position_field_in_subgame_state() -> None:
    import dataclasses

    from thief_peer.services.subgame_state import SubGameState

    names = {f.name for f in dataclasses.fields(SubGameState)}
    assert not any("police_position" in n or "opponent_true" in n for n in names)
