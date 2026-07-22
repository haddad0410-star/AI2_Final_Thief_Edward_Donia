# AI2 Final Project — Thief Peer (thief_peer)

**Status: Implementation Batch 4B (bilateral commitment verification).**
Readiness: `LOCAL_READY`.
`NETWORK_READY`/`LEAGUE_READY`/`SUBMISSION_READY` are **not** claimed — see
`integration_lab/audit/PROGRESS.md` for the authoritative, up-to-date
readiness record.

## Abstract

This repository implements the Thief side of a distributed, partially-observable
pursuit game (Dec-POMDP-flavored) against an independently-built Police peer, per
the course's `police_thief_p2p.pdf` specification. Two fully independent FastMCP
processes communicate over a commit-reveal-sealed wire protocol with no central
referee and no shared mutable state. An initial implementation (Batch 3) produced
strategy code that showed no measurable survival-rate advantage over a baseline —
traced (Batch 3.5) to a real observation-pipeline defect where `_absorb_public_evidence`
read a `police_scent` key that never existed in Police's actual reveal dict, and
hint evidence was never parsed at all; a second defect meant Thief's own honest
capture-claim answer never reached Police over the wire, so capture could never
have been confirmed even after the scent/hint fix alone. Repairing both reversed
the headline result completely (100% → 0% survival rate), which itself turned
out to be a new ceiling tie requiring a dedicated fairness/correctness audit
(Batch 3.6): no exact-position leak via scent (a confident-looking peak matches
the true cell only 30.5% of the time), no premature hint-verdict disclosure, and
— via an 800-game multi-scale robustness check — confirmation that the 0%
survival ceiling is a genuine property of this board/geometry and greedy
pursuit/evasion dynamics, not a defect or a 7×7-specific artifact. Real,
non-ceiling behavioral differences between baseline and advanced strategies were
proven directly (6 deterministic fixtures, never reading the opponent's true
position). Batch 4A adds a live Tkinter GUI (own-truth-only, event-driven,
headlessly-tested view model), a graphical post-game replay viewer built on the
existing unmodified verification engine, a Gmail send-only dry-run reporter
behind a real rate-limiting Gatekeeper, and public-network preparation that is
deliberately never activated. No advanced-strategy win-rate superiority is
claimed anywhere in this repository.

## Team

- Edward Haddad — 214083115
- Donia Naser — 212810493
- Provisional group ID: `edward-donia` (**configurable, requires final verification**
  against the course's binding group-ID assignment rule)

## Sibling repository

This is the **Thief** peer. The **Police** peer lives in a separate, independent
repository (placeholder, not yet created/pushed):
`https://github.com/haddad0410-star/AI2_Final_Police_Edward_Donia`.

Per the project's isolation rules, this repository does **not** import from the
sibling repository or from `integration_lab/` at runtime. Any resemblance in wire
format is by shared protocol contract only (see `docs/PROTOCOL.md`).

## Project objective and problem formulation

Distributed Cops-and-Robbers is framed as a two-agent, partially-observable
pursuit game: a tuple `⟨n, S, {Aᵢ}, P, R, {Ωᵢ}, O, γ⟩` in the Dec-POMDP sense
(book Ch.1.3), where the true joint state `S` is inaccessible to either agent —
"no central observer." Each peer observes only: its own true state, the
opponent's public, decaying scent trail (Ch.4.3, a full-board cumulative trail,
not a local snapshot), and the opponent's (possibly deceptive) natural-language
hint — **never** the opponent's true position. See `integration_lab/audit/protocol_contract.md`
for the full wire-level contract and `integration_lab/evidence/batch3_6/scent_timing_contract.md`
for the book-citation audit behind this formulation.

## Architecture

Two fully independent FastMCP peers (server + client in one OS process each), no
central referee, no shared mutable state, no shared log/config file path. Every
cross-peer message is sealed via SHA-256 commit-reveal before being revealed; a
mutual end-of-game audit recomputes every hash. A local, per-peer state machine
drives every lifecycle transition; illegal transitions are rejected, never
silently ignored. Full detail: `docs/ARCHITECTURE.md`, `docs/PROTOCOL.md`,
`docs/SECURITY.md`.

## Scent and belief model

Scent emission/decay: `τ_ij(t+1) = max(0, (1-ρ)·τ_ij(t) + Δτ_ij)`, emitted every
turn (including STAY), decayed once per round. Belief is a normalized
probabilistic update (prior → transition → barrier mask → scent → hint →
normalize) — explicitly **not** claimed Bayesian-optimal. Structurally guaranteed
(by a signature-introspection test, not just convention) that no belief-update
function ever accepts the opponent's true position. Quantitatively confirmed
(Batch 3.6, 200 real random walks): scent alone produces a uniquely-peaked
candidate reading on 100% of turns, but that peak matches the true position only
**30.5%** of the time — a confident-looking signal, not an exact-position leak,
i.e. the Thief's own true cell is not being exposed to Police through this
channel. Full detail: `docs/BELIEF_MODEL.md`.

## Strategies

- **`BaselineThiefBrain`** — a simple, original, from-scratch greedy baseline.
- **`EntropyEscapeThiefBrain`** — the candidate advanced strategy: full-belief-
  distribution evasion, bounded lookahead, real BFS mobility preservation,
  chokepoint-aware barrier-threat prediction, risk-gated deceptive hints.

Neither is claimed superior to the other on survival rate (see Results below);
`docs/STRATEGY.md` has the full design and `integration_lab/audit/strategy_proposals.md`
the pre-registered evaluation methodology (written before any strategy code
existed, to prevent post-hoc seed selection).

## Results across batches

- **Batch 3**: held-out (100 games) and real-HTTP evaluation showed **100%
  survival rate** for both baseline and advanced Thief — root-caused to a real
  defect (see below), not a strategy-quality finding.
- **Batch 3.5 (pipeline repair)**: found and fixed the real defect — Thief's
  own belief update read a `police_scent` key that never existed in Police's
  actual reveal dict (only `scent_grid` does), plus hint text was never parsed
  into a region at all; also found and fixed a second defect where Thief's
  honest capture-claim answer never reached Police over the wire. After
  repair: **0% Thief survival rate in every matchup** — a complete reversal.
- **Batch 3.6 (fairness/correctness audit)**: verified the 0% result is not
  an artifact — no exact-position leak, no hint-verdict early disclosure,
  correct capture/survival-threshold boundary handling, and (800 games across
  7×7/9×9/11×11) the ceiling is a genuine game-design property that persists at
  every board scale, with mean steps scaling proportionally. 6 deterministic
  fixtures proved `EntropyEscapeThiefBrain` and `BaselineThiefBrain` choose
  genuinely different actions from identical inputs; one scenario honestly
  reports both brains coinciding on the same final action despite real
  per-option mobility differences, rather than being forced into an artificial
  divergence. **Final classification: C (genuine game-design ceiling) with D
  (real behavioral differences) as a corollary** — not A, B, or E. No
  win-rate superiority claim is made. `integration_lab/evidence/batch3_6/conclusion.md`.
- **Batch 4A (reliability regression)**: before any GUI work began, three
  consecutive real six-sub-game HTTP series (advanced vs advanced) all
  completed cleanly (no orphan process, no socket leak, both replay verifiers
  `VERIFIED` throughout), plus one bounded injected-delay scenario proving the
  real deadline/watchdog machinery tolerates a slow-but-legal decision.
  `integration_lab/evidence/batch4a/reliability/`.

## Live GUI (Batch 4A)

`uv run python -m thief_peer peer --gui` launches a live Tkinter view showing
**only this peer's own truth**: own position/path, public barriers (placed by
Police, never a Police true position), local belief heatmap over the opponent
(never a true-position field), sent/received hints, protocol/state-machine
status, decision latency — behind a permanent "LIVE VIEW — OPPONENT TRUE
POSITION HIDDEN" banner. Architecture: the real turn loop publishes typed
events (`services/gui_events.py`) through an optional, off-by-default sink
(`services/gui_sink.py`, same pattern as the existing diagnostic trace hook)
into a thread-safe queue; a pure, Tkinter-free view model (`gui/view_model.py`)
folds events into display state and is headlessly tested (22 tests, including
a reflection-based scanner that fails the build if any GUI-reachable dataclass
grows an `opponent_true_position`-shaped field). The background game loop runs
on its own asyncio event loop in a separate thread so network activity never
blocks the UI. Real two-process runs (a smoke sub-game and a full six-sub-game
series, both `--gui`) completed successfully and replay-verified —
`integration_lab/evidence/batch4a/gui_demo/`. Manual screenshot instructions:
`screenshots/README.md`.

## Graphical replay viewer (Batch 4A)

`uv run python -m thief_peer replay --gui --police-artifacts <dir> --thief-artifacts <dir>`
shows both true trajectories (permitted only here, from finalized audited
artifacts, never live memory), barriers, hints, scores, and a VERIFIED/TAMPERED
banner. It reuses the existing, unmodified `services/replay_verifier.py` for
this peer's own artifacts — a real cross-schema incompatibility was found and
fixed while building this: this repo's own verifier cannot correctly recompute
the opponent's differently-shaped commitment hashes, so the opponent's side is
loaded for display only, honestly labeled `NOT_INDEPENDENTLY_VERIFIED_FROM_THIS_SIDE`,
never a fabricated verdict. A real TAMPERED demonstration (a copy of real
evidence, one field edited) is preserved at
`integration_lab/evidence/batch4a/replay_demo/`; the original evidence was never
touched.

## Gmail reporter (Batch 4A, dry-run only)

`uv run python -m thief_peer report --artifacts-dir <dir>` builds the required
structured-JSON report body (never free text) from real artifact files and
prints it — no network call, no OAuth. `--send` exists in code (routed through
a real token-bucket Gatekeeper with bounded retries/backoff/idempotency) but has
**never been invoked**; it requires `GOOGLE_OAUTH_CREDENTIAL_DIR` (credentials
live outside this repo) and is gated behind Manual Gate C. Scope is hardcoded to
`gmail.send` only — `gmail.modify`/`.compose`/`.readonly`/full-mailbox scopes are
rejected in code, not just documented. The reporter refuses to build a report
from artifacts that fail the real replay verifier (tested,
`integration_lab/evidence/batch4a/gmail_dry_run/invalid_report_rejection.json`).
Mandatory recipient: `rmisegal+uoh26finalgame@gmail.com` (Appendix F Table 20).

## Public-network preparation (Batch 4A, never activated)

`docs/PUBLIC_NETWORK_SETUP.md` and `docs/LEAGUE_RUNBOOK.md` describe what
exists (a tested bearer-token module, `infrastructure/public_auth.py`, constant-
time comparison, env-var-only token) and what deliberately does not (the
server's existing hard localhost-only bind guard is unchanged; no tunnel has
ever been started; no public endpoint has ever been contacted).

## Security

Every step is sealed with SHA-256 commit-reveal over canonical JSON before
being revealed; a mutual end-of-game audit re-verifies every hash, nonce, and
sequence number. Credentials/tokens never live in this repo (`GOOGLE_OAUTH_CREDENTIAL_DIR`/
`PUBLIC_BIND_TOKEN`, both env-var-only, never logged). See `docs/SECURITY.md`.

## Reliability and secondary metrics

Zero-variance, deterministic capture-step counts on the binding board are a
real, reconfirmed property (not a bug) that limits statistical power for
rate-based comparisons — addressed via causal-ablation and behavioral-fixture
methods instead of aggregate rate comparisons. Real non-ceiling differences:
measurable mean reachable-region size (real BFS via
`entropy_escape_utility.reachable_area`) differing by matchup on paired seeds.
Full data: `integration_lab/evidence/batch3_6/secondary_metrics.csv`.

## Limitations

See `docs/LIMITATIONS.md` — kept current every batch, never claiming a
readiness level higher than `integration_lab/audit/PROGRESS.md` supports.

## Reproduction

```
uv sync
uv run pytest
uv run python -m thief_peer peer --no-gui --config-dir config/thief \
  --opponent-url http://127.0.0.1:8901/mcp   # requires police_peer running too
uv run python -m thief_peer peer --gui ...                 # live GUI
uv run python -m thief_peer replay --gui --police-artifacts <dir> --thief-artifacts <dir>
uv run python -m thief_peer report --artifacts-dir <dir>   # Gmail dry-run
uv run python -m thief_peer verify-replay --artifacts <dir>
```

Full reproducibility notes (exact commands, seed ranges) per batch:
`integration_lab/evidence/batch3_6/reproducibility.md`.

## Third-party attribution and licensing caution

See `THIRD_PARTY_NOTICES.md`. Reused elements are limited to small, attributed
adaptations (a commit-reveal hash shape, a token-bucket formula, an OAuth
bootstrap pattern, a protocol naming convention) — never substantial verbatim
code. Full classification: `integration_lab/audit/reference_reuse_plan.md`.
**Repository visibility (public vs. private) is an unresolved decision**
(Manual Gate E) — the reference repository's EULA does not unambiguously
authorize redistributing adapted/attributed elements into a separate public
repository; do not make this repository public without your explicit review.

## Current readiness and remaining manual gates

**`LOCAL_READY`.** Not `NETWORK_READY`/`LEAGUE_READY`/`SUBMISSION_READY`.
Remaining, all requiring your explicit action (`integration_lab/audit/manual_gates.md`):
Gate A (public endpoint + tunnel token), Gate B (real opponent identity/URL/schedule),
Gate C (Gmail OAuth consent + send approval), Gate E (repository visibility),
Gate F (GitHub repo creation/push).
