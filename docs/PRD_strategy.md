# PRD strategy

## Purpose

Define the strategy seam and the two brains for this role.

## Requirements

- `BrainBase` contract: `_pick_move(moves, state, belief) -> Decision`, legal-move-only output, deadline-aware, deterministic test mode.
- `BaselineThiefBrain`: simple, original, from-scratch greedy baseline.
- `EntropyEscapeThiefBrain`: candidate original design, implemented and used in real
  gameplay — see `_post4b_supplementary_evidence/audit/strategy_proposals.md` Section 3/4 for the full sketch (the pre-registered design methodology, written before any strategy code existed).
- Move is always pure Python; LLM banter is optional, template provider by default (0 tokens).

## Acceptance criteria (measurable)

- [x] Both brains never return an illegal move across a large randomized test sweep — `tests/unit/test_baseline_thief_brain.py::test_always_returns_a_legal_move_over_random_boards`, `tests/unit/test_entropy_escape_brain.py::test_always_returns_legal_move_across_random_scenarios`.
- [x] Both brains always return within the deadline (fallback tested) — `tests/unit/test_baseline_thief_brain.py::test_deadline_compliance_is_fast`, `tests/unit/test_entropy_escape_brain.py::test_deadline_fallback_never_exceeds_budget`.
- [x] Experiments compare candidate vs. baseline on held-out/pre-registered seeds only, with raw data saved — no claim without it; see `docs/EXPERIMENTS.md` and `_post4b_supplementary_evidence/audit/strategy_proposals.md` (pre-registered methodology, written before any strategy code existed). No survival-rate superiority is claimed for either brain (both ceiling-tied at 0%); real non-ceiling behavioral differences are demonstrated by 6 deterministic fixtures.

## Out of scope (for now)

LLM-driven move selection (never in scope unless a signed mutual rule with the opponent explicitly enables it).

Status: implemented, tested, and used in real gameplay (`BaselineThiefBrain` and
`EntropyEscapeThiefBrain` both wired via `[strategy]` config). See
`_post4b_supplementary_evidence/audit/PROGRESS.md`.
