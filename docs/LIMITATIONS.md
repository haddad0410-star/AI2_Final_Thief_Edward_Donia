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
