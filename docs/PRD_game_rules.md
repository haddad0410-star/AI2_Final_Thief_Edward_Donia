# PRD game rules

## Purpose

Define local game physics: board, movement, barriers, scoring, series structure.

## Requirements

- 7x7 board minimum, 4-orthogonal+STAY movement only, no diagonals (Appendix F Table 13/15, visually confirmed).
- Barrier placement restricted to the police's own cell or an orthogonally-adjacent cell; permanent; truthful declaration mandatory; placing on the thief's current cell is a capture (Ch.3.4 "Barrier Law", visually confirmed — see `_post4b_supplementary_evidence/audit/visual_verification.md`).
- max_barriers=14, max_moves=35, survival_threshold=35 (all minimums).
- Scoring: capture_cop=20, capture_thief=5, survival_cop=5, survival_thief=10, tie_score=2 (all constants); technical_loss=0 (cross-confirmed, not a numbered Appendix F row).
- num_games=6 per series (constant, visually confirmed).

## Acceptance criteria (measurable)

- [x] All legal-move generation matches the negotiated `move_set` — `domain/rules.py::legal_move_directions`, `tests/unit/test_rules.py` (15 tests, incl. diagonal rejection, boundary rejection, barrier collision).
- [x] Barrier placement legality tests pass (adjacency + permanence + no self-removal) — `domain/rules.py::is_legal_barrier_cell`/`place_barrier`, same test file; see also `docs/adr/ADR-0011-trapped-thief-interpretation.md` for the STAY-always-legal interpretation.
- [x] Scoring unit tests match the table above exactly — `domain/scoring.py`, `tests/unit/test_scoring.py` (4 tests).
- [x] A 6-sub-game series runs to completion locally — real bilateral six-sub-game HTTP series completed repeatedly against the Police peer (Batch 4B), including a real independent bilateral result-agreement exchange; see `_post4b_supplementary_evidence/batch4b/bilateral_series/`. (Batch 1's negotiation-handshake-only smoke test, a development-workspace artifact not included in this standalone package, has since been superseded.)

## Turn-cap vs. real outcomes (Batch 2, session recovery step A)

`survival_threshold` (from the binding shared `game.json`) is the only source
of truth for how many turns a real sub-game plays before survival is scored.
A local/test `max_turns` cap smaller than that is not a game rule and must
never be reported as a real survival or capture outcome: `SubGameRuntime`
scores it as an explicit `TECHNICAL_LOSS` with no audit, distinct from a
protocol-error technical loss only by its `reason` string
(`"turn cap exhausted before a natural sub-game outcome"`). See
`docs/ARCHITECTURE.md` for the full exit-path table.

## Out of scope (for now)

Scent/belief model (see PRD_scent_belief.md — now implemented). Cryptographic sealing
(see PRD_commit_reveal.md — now implemented and tested).

Status: board/rules/scoring implemented and tested (Batch 1); the full game loop that
plays a sub-game (and a full six-sub-game series) to completion is implemented and has
been run repeatedly against the Police peer over real FastMCP HTTP. See
`_post4b_supplementary_evidence/audit/PROGRESS.md`.
