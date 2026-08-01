# Strategy — Thief Peer (role-local summary)

**Canonical source:** `_post4b_supplementary_evidence/audit/strategy_proposals.md` — read that first
for the full design, invariants, complexity limits, and evaluation metrics.

This role ships two brains, both implemented (Implementation Batch 3):

1. **`BaselineThiefBrain`** — a simple, original, from-scratch greedy baseline.
   Not a copy of the reference repository's shipped heuristic. Frozen (Batch 3
   Task 2, regression-tested) as the comparison point for the strategy below.
2. **`EntropyEscapeThiefBrain`** (`strategy/entropy_escape_thief_brain.py`) — original
   advanced strategy. Batch 3 found no demonstrated survival-rate improvement
   (both baseline and advanced reached 100% survival), root-caused to a real
   observation-pipeline defect (full write-up produced during development
   in the full project workspace; not included in this single-repo
   package) — since repaired in **Implementation Batch 3.5** (likewise
   documented during development, not included in this single-repo
   package), which also
   found and fixed a second real defect: Thief's honest capture-claim answer
   was never actually delivered back to Police over the wire (`claim_response`
   was always `None`), meaning capture could never have been confirmed in
   real play even after the scent/hint fix alone. Held-out and real-HTTP
   re-evaluation now shows **0% survival for both baseline and advanced
   Thief, against either Police strategy** (a new ceiling tie at the losing
   end) — `EntropyEscapeThiefBrain` shows no demonstrated improvement over
   baseline in this configuration. Full analysis was produced during
   development in the full project workspace; not included in this
   single-repo package. Reported honestly, not hidden. This is a genuinely more sophisticated,
   tested implementation, but no survival superiority claim is made.
   **Implementation Batch 3.6** ran a dedicated fairness/correctness audit
   on top of this result: an 800-game multi-scale robustness check (7x7
   alt-start, 9x9, 11x11, all `RESEARCH_ONLY`) confirmed the 0%-survival
   ceiling persists at every board scale tested — a genuine game-design
   property, not a 7x7-specific artifact — and 6 deterministic behavioral
   fixtures (no true-opponent-position access) proved
   `EntropyEscapeThiefBrain` and `BaselineThiefBrain` genuinely choose
   different actions from identical inputs. Final classification: **C**
   (genuine ceiling) **with D** (real behavioral differences) **as a
   corollary** (full write-up produced during development in the full
   project workspace; not included in this single-repo package).

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
