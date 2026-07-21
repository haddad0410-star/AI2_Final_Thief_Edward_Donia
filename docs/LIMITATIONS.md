# Limitations — Thief Peer

Current, honest state as of this scaffold (Phase 1-2, no application code written):

- No FastMCP server/client exists — nothing here has run over real HTTP yet.
- No game engine, state machine, strategy, scent/belief model, cryptography, GUI,
  replay, or Gmail sender is implemented.
- `pheromone_min_center_intensity=0.5` (seen in the reference repo's config) is not
  confirmed as a binding Appendix F value — tracked as an open item, not assumed.
  See `integration_lab/audit/risk_register.md` risk #2.
- Repository visibility (public vs. private) and its licensing implications are
  unresolved pending your decision — see `integration_lab/audit/manual_gates.md`
  Gate E.
- No league opponent, public network exposure, or Gmail send has occurred.

This file will be kept current every phase — never allowed to go stale while claiming
a higher readiness level than `integration_lab/audit/PROGRESS.md` supports.

## Current state (Implementation Batch 3.6)

- A dedicated epistemic-fairness, scent-timing, capture-correctness, and
  strategy-distinguishability audit was run on top of Batch 3.5's repair,
  triggered by Batch 3.5's own headline result (0% Thief survival / 100%
  Police capture in every matchup) being a **new ceiling tie in the
  opposite direction** — technically successful, scientifically
  inconclusive about strategy quality on its own.
- **No exact-position leakage found**: a real 200-random-walk quantitative
  simulation over production `domain.scent`/`domain.belief_updates` code
  shows scent produces a uniquely-peaked candidate reading on 100% of
  turns, but that peak matches the true opponent position only **30.5%**
  of the time, and belief entropy barely drops (5.61 -> 5.36 bits) — a
  confident-looking maximum-likelihood signal, not a leak of the true
  cell — meaning the Thief's own position is not being exposed to Police
  through this channel. `integration_lab/evidence/batch3_6/epistemic_leakage_audit.md`.
- **No hint-verdict early-visibility defect found**: the intent
  (truth/lie) verdict is confirmed absent from the live `reveal` payload
  and present/verifiable only at final audit, both by direct code
  inspection and 3 new end-to-end tests.
- **800-game multi-scale robustness check** (7x7 alt-start, 9x9, 11x11;
  RESEARCH_ONLY, never replacing the binding 7x7 league config) confirms
  the 0%-survival ceiling is a genuine **game-design property of this
  board/geometry and greedy pursuit/evasion dynamics**, not a
  7x7-specific implementation artifact — mean steps to outcome scale
  proportionally with board size (12 -> 16 -> 20), giving the Thief more
  room but not survival, at every scale tested.
- Real behavioral differences between baseline and advanced strategies
  **do exist** even though they don't move the survival-rate ceiling: 6
  deterministic action-divergence fixtures (no true-opponent-position
  access) prove `EntropyEscapeThiefBrain` genuinely chooses differently
  from `BaselineThiefBrain` given identical inputs, including real
  per-option mobility variation computed via the real
  `entropy_escape_utility.reachable_area` bounded-BFS function.
- One process error was self-caught and disclosed: the existing (Batch
  3.5-scoped) capture-sanity script regenerated Batch 3.5's evidence
  files in place before being replaced with a properly-scoped Batch 3.6
  version; content was verified materially identical. One real HTTP
  series showed a transient sub-game failure (system-load-dependent,
  reproduced 0 times on a clean rerun); both are disclosed in
  `integration_lab/evidence/batch3_6/limitations.md` and
  `.../real_http/transient_flake_note.md`.
- Final classification: **C (genuine game-design ceiling, honestly
  documented) with D (real behavioral differences exist) as a direct
  corollary** — not A/B/E. See
  `integration_lab/evidence/batch3_6/conclusion.md`.
- Full evidence set: `integration_lab/evidence/batch3_6/` (scent-timing
  contract with book page citations, leakage audit, hint-visibility
  audit, causal ablation across 9 evidence-source conditions, capture-
  correctness re-audit, 6 behavioral fixtures, secondary metrics, 800-game
  robustness results, research/production equivalence, real HTTP series,
  7 figures).
- Readiness: `LOCAL_READY` (unchanged — Batch 3.6 is a fairness/
  correctness audit on top of an already-`LOCAL_READY` baseline;
  `NETWORK_READY`/`LEAGUE_READY`/`SUBMISSION_READY` still not claimed).

## Current state (Implementation Batch 3.5)

- The observation-pipeline defect identified in Batch 3 (below) is
  **repaired**: real scent/hint evidence now genuinely reaches belief
  updates over the real wire protocol (`_absorb_public_evidence` was
  reading a `police_scent` key that did not exist in Police's actual
  reveal dict — a real field-name mismatch bug, fixed alongside adding the
  missing hint-region decode). A real, additional defect was also found
  and fixed: the honest answer to a police capture claim
  (`pending_claim_response`) was never actually delivered back to Police
  over the wire (same class of bug as the scent one) — meaning **capture
  could never have been confirmed in real play even after the scent/hint
  fix alone**. Fixing this required a genuine one-turn-delayed
  confirmation design (the synchronous per-step exchange structurally
  cannot answer a same-step claim), found and fixed while building Task
  9's real-HTTP capture sanity fixtures.
- Held-out evaluation (400 games) and real HTTP validation (18 sub-games)
  now show **0% Thief survival rate in every matchup** — capture is now
  reliably reachable, a complete reversal from Batch 3's 100% survival.
  `EntropyEscapeThiefBrain` shows **no demonstrated improvement** over
  `BaselineThiefBrain` in this held-out configuration (both 0% survival,
  ceiling-tied at the losing end, against both baseline and advanced
  Police) — reported honestly, not hidden.
- Full analysis: `integration_lab/evidence/batch3_5/` (root cause, audit,
  before/after traces, capture sanity fixtures, held-out and real-HTTP
  results, figures).
- Readiness: `LOCAL_READY` (unchanged — Batch 3.5 repairs a functional
  defect and re-validates on top of an already-`LOCAL_READY` baseline;
  `NETWORK_READY`/`LEAGUE_READY`/`SUBMISSION_READY` still not claimed).

## Current state (Implementation Batch 3)

- `EntropyEscapeThiefBrain` is implemented, unit-tested (21 tests), and
  validated over 3 real six-sub-game HTTP series — but held-out research
  evaluation (100 games) and the real HTTP series both found **no
  demonstrated survival-rate improvement** over `BaselineThiefBrain` in the
  current experimental configuration (both already 100% survival, including
  against the advanced police opponent). Root cause: the real wire protocol
  does not currently deliver scent or hint signal to either brain's belief
  update, so police pursuit rarely converges within the 35-move budget
  regardless of thief strategy quality — a pre-existing system
  characteristic, not a defect in this batch's strategy code. Full
  analysis: `integration_lab/evidence/batch3/strategy_research/limitations.md`.
- A real, pre-existing bug was found and fixed this batch:
  `services/subgame_deps.py::make_deps` always hardcoded
  `BaselineThiefBrain` regardless of the private config's `thief_class`
  field, which was parsed but never actually consulted anywhere in the
  real `run-subgame`/`run-series` path. Now genuinely wired — see
  `CHANGELOG.md`.
- GUI, Gmail reporting, public network exposure, and league play remain
  not implemented/run, unchanged from session recovery step C.
- `pheromone_min_center_intensity=0.5` remains unconfirmed as binding (risk
  #2, unchanged). Repository visibility/licensing consent (Manual Gate E)
  remains unresolved, unchanged.
- Readiness: `LOCAL_READY` (unchanged from session recovery step C — Batch
  3 adds strategy work on top of an already-`LOCAL_READY` local P2P
  baseline; `NETWORK_READY`/`LEAGUE_READY`/`SUBMISSION_READY` still not
  claimed).

## Current state (session recovery step C)

- Implemented and independently verified: config loading, domain
  models/board physics, scent/belief, protocol schemas, commit-reveal
  sealing, canonical `declaration/2` Step-0 declaration, state machine,
  deadline tracker, watchdog, baseline strategy brain, template hints,
  sub-game runtime, series runtime, JSON artifact generation, headless
  replay verifier, and full CLI wiring.
- **New this step**: a real two-process game/series against the actual
  Police opponent (one sub-game and a full six-sub-game series, both over
  real FastMCP HTTP), and the mutual cross-repo artifact/audit comparison
  (96/96 checks passed) — both previously unimplemented/unrun, now done.
  Six real cross-repo protocol/wiring defects were found and fixed only by
  actually running two independent processes against each other — see
  `CHANGELOG.md` and `integration_lab/audit/risk_register.md` risks #15-#16.
- **Still not implemented or run**: `EntropyEscapeThiefBrain` (only the
  from-scratch baseline exists), a live GUI, a replay *viewer* (the
  headless verifier exists; a visual viewer does not), Gmail reporting,
  public network exposure/tunnel, and league play.
- The live cross-process path for `run-subgame`/`run-series` **is now
  validated** — see `integration_lab/evidence/session_recovery_step_c/`.
- The declaration schema divergence between this repo and the Police repo
  (risk #14) is **resolved** — canonical `declaration/2`, verified
  byte-identical fixtures.
- `pheromone_min_center_intensity=0.5` remains unconfirmed as binding (risk
  #2, unchanged from Batch 1).
- Repository visibility/licensing consent (Manual Gate E) remains
  unresolved, unchanged from Batch 1.
- Readiness: `LOCAL_READY` (session recovery step C). `NETWORK_READY`/
  `LEAGUE_READY`/`SUBMISSION_READY` not claimed.
