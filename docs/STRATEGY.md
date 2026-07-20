# Strategy — Thief Peer (role-local summary)

**Canonical source:** `integration_lab/audit/strategy_proposals.md` — read that first
for the full design, invariants, complexity limits, and evaluation metrics.

This role ships two brains, both implemented (Implementation Batch 3):

1. **`BaselineThiefBrain`** — a simple, original, from-scratch greedy baseline.
   Not a copy of the reference repository's shipped heuristic. Frozen (Batch 3
   Task 2, regression-tested) as the comparison point for the strategy below.
2. **`EntropyEscapeThiefBrain`** (`strategy/entropy_escape_thief_brain.py`) — original
   advanced strategy. **Held-out and real-HTTP evaluation found no demonstrated
   survival-rate improvement over the baseline** in the current experimental
   configuration (both already reach 100% survival, including against the
   advanced police opponent) — see
   `integration_lab/evidence/batch3/strategy_research/limitations.md` for the
   root-cause analysis. Reported honestly, not hidden. This is a genuinely
   more sophisticated, tested implementation, but no superiority claim is made.

### `EntropyEscapeThiefBrain` design

Uses the COMPLETE belief distribution about the believed police location,
not just its single most-likely cell:

- **Capture-risk minimization**: scores each legal move by the increase in
  expected Manhattan distance from the believed police location.
- **Bounded lookahead** (`entropy_escape_utility.py::project_belief`, depth
  2 by default): propagates belief forward via the same `apply_transition`
  primitive the real belief pipeline uses, scoring moves by projected
  post-lookahead expected distance too.
- **Mobility preservation**: real BFS-based reachable-region size
  (`entropy_escape_utility.py::reachable_area`) plus immediate open-neighbor
  count, rewarding cells that keep more future escape routes open.
- **Barrier-threat prediction** (`entropy_escape_utility.py::barrier_threat`):
  since this peer never knows the police's true position, exposure is
  estimated structurally — proximity to the believed-likely police region ×
  how few open neighbors the candidate cell itself has (a chokepoint proxy).
- **Trajectory control**: a revisit penalty and a straight-line-repeat
  penalty (tracked via a bounded recent-direction history) discourage
  predictable paths, without ever fabricating a physical/cryptographic
  field.
- **Risk-gated deceptive hints**: uses the existing offline template hint
  system only (no LLM). Selects `HintIntent.LIE` when the chosen
  destination's residual believed-police probability exceeds a configurable
  threshold, `HintIntent.TRUTH` otherwise — the move itself, and every
  physical/cryptographic field, is always truthful regardless of hint intent.
- **Utility weights** are a documented, private dataclass
  (`entropy_escape_config.py::EntropyEscapeWeights`) — never hardcoded
  inline, never part of the signed shared `game.json`. Selected via each
  peer's own `game.toml` `[strategy]` table (`profile`/`weights`).
- **Safety**: `decide()` wraps `_decide()` in a try/except, falling back to
  the first legal direction (or `STAY`) on any internal error — always
  returns a legal action before the deadline.

## Seam

Both subclass a shared `BrainBase` and override `_pick_move` (and optionally
`_decide_move`), invoked strictly between hint-parsing and commit-sealing — the move
is always pure Python; an LLM, if enabled at all, only writes banter text.

## Default banter provider

`template` (0 tokens, no network, no paid API). Any paid provider
(`claude_api`/`claude_cli`/`ollama`) is opt-in only, disabled by default in
`config/thief/game.toml`.
