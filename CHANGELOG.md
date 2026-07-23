# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Fixed — Post-Batch-4B manual screenshot finalization

- **Peer-startup readiness race**: `peer --gui`/`run-series`/`run-subgame`
  sent the first real commit before the opponent's server/state machine
  was necessarily ready, causing a spurious `TECHNICAL_LOSS` on ordinary
  two-terminal human timing. Fixed with a bounded opponent-health wait
  (`services/subgame_runtime.py::SubGameRuntime._await_opponent_ready`,
  reusing the existing `wait_for_health`) placed correctly — right after
  this peer's own machine leaves `INITIALIZING` (so it stays receptive to
  the opponent's first message the entire time it waits), never gated
  behind it. A genuine no-show still fails honestly at the first real
  turn call, unchanged.
- **GUI protocol-status panel showed nothing real**: `commit_sent`/
  `ack_received`/`reveal_sent`/`reveal_received` existed in the view model
  but `gui/tk_panels.py`'s `StatusPanel` never rendered them, and
  `services/turn_gui_publish.py` had hardcoded `commit_sent=True` and
  collapsed the other three onto one pass/fail flag. Fixed: new
  `services/turn_exchange.py` (`deliver_commit_and_reveal`,
  `ExchangeProgress`, `ExchangeError`) tracks the REAL per-substep
  progress of each commit/reveal exchange, `turn_gui_publish.py` reads it
  instead of hardcoding, and `tk_panels.py` renders all four. New
  `tests/unit/test_turn_exchange.py` and `tests/unit/test_turn_gui_publish.py`
  prove the values differ correctly across distinct real failure modes.
- **`McpError` (client-side session-initialize timeout) crashed instead of
  retrying**: the readiness fix above calls `wait_for_health` far more
  often than before, which newly exposed a pre-existing gap in
  `infrastructure/mcp_client.py` — a connection/session-initialization
  timeout (`"Timed out while waiting for response to InitializeRequest"`)
  is raised by the installed `mcp`/`fastmcp` packages as `McpError`, which
  wasn't in `_CONNECTION_FAILURES` and so propagated uncaught instead of
  becoming `PeerUnavailableError`. Fixed narrowly: only an `McpError`
  whose `error.code == httpx.codes.REQUEST_TIMEOUT` (the exact, verified
  code used by the only two client-side-timeout raise sites in the
  installed packages) is reclassified as `PeerUnavailableError`; any other
  `McpError` (a genuine remote/application error) still propagates
  unchanged. New `tests/unit/test_mcp_client.py` (6 tests, fully
  monkeypatched/deterministic). The regression this fixes: a real
  integration test that used to take 30.17s (retry-then-crash) now takes
  0.2-0.5s.
- New non-destructive `config/thief_advanced` profile (identical to
  `config/thief` except `[strategy].thief_class` points at
  `EntropyEscapeThiefBrain`) paired with Police's advanced profile so the
  barrier-placement screenshot is actually reachable. The default
  `config/thief` profile itself was never modified.
- 18 real, human-captured screenshots (9 per repo) added under
  `screenshots/`; both `screenshots/README.md` files corrected where they
  previously pointed at commands that couldn't produce the described
  capture. Full index: `integration_lab/evidence/batch4b/MANUAL_HANDOFF.md`.
- 458 tests, 91.89% coverage, 0 Ruff violations, all files <=150 meaningful
  lines.

### Added — Implementation Batch 4B (bilateral commitment verification)

- **Unified `commitment/1` sealed-record schema** (`domain/sealing/payload.py`):
  resolves the Batch 4A cross-schema finding — the opaque `state` digest
  string replaced by a flat `position` field (dropping the `visited`
  counter, never itself part of the binding field set; preserved verbatim
  for legacy records via a new `legacy_state` passthrough field so old
  hashes still recompute exactly). Schema-version-aware
  `to_canonical_dict()` keeps all Batch 1-4A evidence self-verifiable
  unmodified.
- **Real bilateral verification**: `services/bilateral_verify.py` (new,
  shared by the GUI replay viewer and the Gmail report gate) lets this
  repo's own crypto module independently verify a genuine Police
  `commitment/1` record, no cross-repo import. New role-consistency
  (`_check_role_fields`) and unknown-field (`_check_unknown_fields`)
  checks in `services/replay_checks.py`. `VerdictBanner` now shows
  `VERIFIED — BOTH PEERS INDEPENDENTLY VERIFIED` when both sides are
  fully bilaterally verified.
- **Gmail report bilateral gate**: `report --opponent-artifacts-dir <dir>`
  refuses to build a report unless full bilateral verification passes.
- Evidence: `integration_lab/evidence/batch4b/` — schema audit, 10
  byte-identical cross-repo test vectors, a 21-category bilateral tamper
  matrix (all detected, both directions), a real six-sub-game two-process
  FastMCP series with `FULL_BILATERAL_VERIFICATION=true` both sides, and
  bilaterally-gated Gmail dry-run evidence.
- 444 tests, 0 Ruff violations, all files <=150 meaningful lines.

### Added — Implementation Batch 4A (live GUI, replay viewer, Gmail
### dry-run reporting, public-network preparation)

- **Live GUI** (`gui/`, `services/gui_events.py`, `services/gui_sink.py`,
  `services/turn_gui_publish.py`, `services/turn_prep.py`): the real turn
  loop now optionally publishes typed, own-truth-only events through an
  off-by-default sink into a thread-safe queue; a pure Tkinter-free view
  model (`gui/view_model.py`) folds them into display state (22 headless
  tests, including a reflection-based opponent-position-leak scanner).
  `services/turn_loop.py` gained publish calls; split
  `turn_prep.py`/`turn_gui_publish.py` out to stay under the 150-line cap.
  New `peer --gui`/`--no-gui` CLI command (`sdk/gui_runner.py`,
  `gui/tk_app.py`/`tk_board.py`/`tk_panels.py`, `gui/background_runner.py`,
  `cli_batch4a.py`). Real two-process runs (smoke + full six-sub-game
  series, `--gui`) completed and replay-verified.
- **Graphical replay viewer** (`gui/replay_view_model.py`,
  `gui/replay_steps.py`, `gui/replay_playback.py`,
  `gui/tk_replay_app.py`/`tk_replay_board.py`/`tk_replay_panels.py`, new
  `replay` CLI command): reuses `services/replay_verifier.py` unmodified.
  **Real defect found and fixed while building this**: this repo's own
  verifier cannot correctly recompute the opponent's differently-shaped
  (`commit-reveal/2` vs `sealed-turn/2`) commitment hashes, and would
  otherwise report a false TAMPERED on genuinely valid opponent data — the
  opponent's side is now loaded for display only, honestly labeled
  `NOT_INDEPENDENTLY_VERIFIED_FROM_THIS_SIDE`, never a fabricated verdict.
  15 headless tests.
- **Gmail dry-run reporter** (`domain/gmail_report_schema.py`,
  `infrastructure/gmail_credentials.py`, `infrastructure/gmail_gatekeeper.py`,
  `infrastructure/gmail_sender.py`, `sdk/report_runner.py`, `cli_gmail.py`,
  new `report` CLI command): structured-JSON report built from real
  artifacts; `gmail.send`-only scope enforced in code; real token-bucket
  Gatekeeper (rate limit, concurrency, bounded retries/backoff, queue
  depth, idempotency); refuses to build a report from artifacts that fail
  the real replay verifier. `--send` exists but was never invoked this
  batch (43 tests across gatekeeper/credentials/sender/schema/refusal).
  New optional `gmail-send` dependency group (google-auth/-oauthlib/
  api-python-client), never installed by default `uv sync`.
- **Public-network preparation, never activated**
  (`infrastructure/public_auth.py`, `docs/PUBLIC_NETWORK_SETUP.md`,
  updated `docs/LEAGUE_RUNBOOK.md`): bearer-token resolution/constant-time
  verification, tested (7 tests). The existing localhost-only bind guard
  in `infrastructure/server_lifecycle.py` is unchanged.
- **Reliability regression** (before any GUI work began, per explicit
  gating instruction, run once for the whole workspace): three
  consecutive real six-sub-game HTTP series plus one bounded
  injected-delay scenario all passed cleanly.
- Workspace scripts (`integration_lab/scripts/`): `check_public_endpoint.py`,
  `check_peer_auth.py`, `check_port_release.py`, `package_match_evidence.py`
  — all preparation/verification only, no network calls, no packaging of
  unverified evidence.

### Added — Implementation Batch 3.6 (epistemic fairness, scent timing,
### capture correctness, and strategy distinguishability audit)

No production defects were found this batch (verification/audit only,
triggered by Batch 3.5's own 0%-survival ceiling result needing an
independent fairness check before being trusted).

- `tests/unit/test_hint_visibility_batch3_6.py` (3 tests): end-to-end
  proof that the hint intent verdict is absent from the live `reveal`
  payload and present/verifiable only at final audit.
- `tests/unit/test_capture_correctness_batch3_6.py` (1 test): boundary
  proof that a truthful capture claim delivered on the exact same turn
  survival would otherwise trigger still resolves as `CAPTURE`.
- Corrected a documentation-only inaccuracy in
  `integration_lab/audit/protocol_contract.md` §3.2: the `scent_grid`
  field name was a project paraphrase of the book's prose, not a literal
  book-mandated identifier (confirmed via full-text PDF search) — the
  implemented field/semantics are unchanged.
- Full audit evidence (no code impact): quantitative information-leakage
  analysis (200 random walks over production `domain.scent`/
  `domain.belief_updates`), a 9-condition causal ablation harness, 6
  deterministic strategy behavioral-difference fixtures (built honestly —
  one scenario's first construction showed no divergence and was
  iterated, another was found to have a barrier-filtering bug in a
  reimplemented helper and was fixed by reusing the real
  `entropy_escape_utility.reachable_area` directly), non-ceiling secondary
  metrics, an 800-game multi-scale `RESEARCH_ONLY` robustness check, 3 new
  research/production-equivalence tests, and a 4-series real HTTP
  validation run. See `integration_lab/evidence/batch3_6/`.

### Fixed — Implementation Batch 3.5 (observation-pipeline repair)

- `domain/sealing/payload.py::SealedTurnPayload` gained a real `scent_grid`
  field (schema `sealed-turn/2`); the raw scent grid now actually crosses
  the wire in the reveal body, alongside the existing digest.
- `services/turn_loop.py::_absorb_public_evidence` now reads
  `opp.get("scent_grid")` (was reading a `police_scent` key that never
  existed in Police's real reveal dict — a real field-name mismatch bug,
  the root cause of Thief's belief never receiving real scent evidence)
  and decodes the received hint's region via the new
  `domain/hint_region.py`.
- **Real defect found and fixed**: the honest answer to a police capture
  claim (`resolve_capture`'s `response`) was computed but never actually
  included in Thief's own outgoing payload — `claim_response` was always
  `None`. Fixed via a genuine one-turn-delayed confirmation design (the
  synchronous per-step commit/reveal exchange structurally cannot answer a
  same-step claim, since both peers send their own reveal before
  receiving the other's): `SubGameState.pending_claim_response` is set
  when a claim/barrier is evaluated and delivered in the NEXT turn's
  reveal; an already-captured thief sends one final confirming reveal
  (no further real move) before terminating. Found while building Task
  9's real-HTTP capture sanity fixtures — this means **capture could
  never have been confirmed to Police in real play**, independent of the
  scent/hint fix.
- `intent` removed from `public_reveal_dict()` — now sealed until the
  final audit like `nonce`, per the "truth/lie intent sealed" rule.
- New `domain/scent_validation.py` and `domain/hint_region.py`
  (region-word encode/decode, including `generate_for_direction` so a
  lying hint embeds a genuinely wrong region — previously the region word
  was always true regardless of intent, undermining the deception
  mechanic).
- `services/belief_update.py::update_belief` now returns
  `(belief, updated_hint_trust)` — consistency-based hint-trust tracking
  (entropy-delta), never derived from the sealed `intent` field.
- New tests covering scent/hint transport, belief order, capture-response
  delay, and strategy-pipeline integration — 325 -> 352 tests, coverage
  94.18% -> 93.87%; see `integration_lab/evidence/batch3_5/quality/`.
- Held-out (400 games) and real-HTTP (18 sub-games, 3 series) results:
  Thief survival rate 100% -> 0% in every matchup (capture now reliably
  reachable; `EntropyEscapeThiefBrain` shows no demonstrated improvement
  over baseline in this configuration, honestly reported). Full analysis:
  `integration_lab/evidence/batch3_5/`.

### Added — Implementation Batch 3

- `strategy/entropy_escape_thief_brain.py` (+ `entropy_escape_config.py`,
  `entropy_escape_utility.py`): original advanced Thief strategy.
  Full-belief-distribution evasion (not just argmax), bounded belief-
  transition lookahead, real BFS-based mobility/reachable-region scoring,
  a structural barrier-threat proxy (proximity to believed police region ×
  local chokepoint-ness), a trajectory-predictability penalty, risk-gated
  deceptive hint selection (existing template system only — no LLM), and a
  documented, configurable utility function. 21 unit tests.
- `strategy/loader.py::build_strategy`/`load_strategy_class` gained an
  interface check (`decide(ctx)` callable) and an optional `weights`
  parameter, passed through only when the resolved class's constructor
  accepts one.
- `shared/private_config.py::StrategyConfig` gained `profile`
  (`baseline`/`advanced`/`experiment`) and `weights` (validated numeric-
  only, unknown-key-rejecting) fields, selected via each peer's own private
  `game.toml` — never the signed shared `game.json`.
- **Real bug found and fixed**: `services/subgame_deps.py::make_deps` had
  always hardcoded `BaselineThiefBrain` regardless of the private config's
  `thief_class` setting — the field was parsed but never actually
  consulted anywhere in the real `sdk/game_runner.py` call path. Fixed:
  `make_deps` now accepts `strategy_class`/`strategy_weights` and both
  `run_subgame_headless`/`run_series_headless` thread
  `private.strategy.thief_class`/`.weights` through for real.
- Held-out research evaluation (100 games, seeds 2000-2099) and 3 real
  six-sub-game HTTP series found **no demonstrated survival-rate
  improvement** over `BaselineThiefBrain` in the current experimental
  configuration (both already achieve 100% survival, including against
  the advanced police opponent) — documented as ceiling-tied/inconclusive
  in `integration_lab/evidence/batch3/strategy_research/limitations.md`,
  not hidden.
- `integration_lab/strategy_research/` (research-only local simulator,
  leakage tests, experiment runner, statistics, figures) and
  `integration_lab/run_advanced_strategy_series.py` (real HTTP validation
  launcher) — see `integration_lab/evidence/batch3/`.

### Changed — Session recovery step C

- Declaration schema frozen as canonical, versioned `declaration/2`
  (resolves `integration_lab/audit/risk_register.md` risk #14).
  `domain/declaration.py` rewritten and split (150-line cap) into
  `declaration.py` (dataclass/to_dict/validate), `declaration_parsing.py`
  (`parse_declaration`, strict allow-list, alias normalization),
  `declaration_builder.py` (`DeclarationContext`/`build_declaration`, plus
  `git_commit_hash`/`code_version` moved in), `declaration_checks.py`
  (`declaration_mismatches`, split out). `domain/hardware.py`'s
  `HardwareInfo` gained `gpu_available`/`vram_status` (never fabricated —
  `None` + explanatory status when unavailable; `vram_gb` already existed).
  New `content_sha256` commitment field. `services/series_artifacts.py`
  updated to the new `DeclarationContext` call site.
  `declaration/1`-era aliases (`commit_hash`, `config_sha256`) accepted on
  input only, normalized, rejected if ambiguous. Canonical JSON Schema
  published at `docs/schemas/declaration.schema.json`, byte-identical
  (SHA-256 `a995d657e81ed920f87f3ef39c3281550d346f38c18468cf7fdee79cd42a97bd`)
  to the independently-built Police repo's copy; cross-repo fixture
  equivalence verified by
  `integration_lab/scripts/compare_declaration_schemas.py`. 22 tests in
  `tests/unit/test_declaration.py`. 281 -> 292 tests, both Ruff/format
  clean. See
  `integration_lab/evidence/session_recovery_step_c/task2_declaration_schema/`
  and `.../declaration_schema_audit.md`.

### Added — Session recovery step B

- `services/series_runtime.py` (Phase 10): six-sub-game series runtime.
  Shares one `PeerStateMachine` across sub-games (new `machine` parameter
  on `run_series()`/`SubGameRuntime.__init__`/`SubGameState.initial`, and a
  new `bootstrap` parameter on `SubGameRuntime.run()`), so a caller's own
  incoming-message server and the local turn loop stay in sync. Fresh local
  state (position/scent/belief/board/step/records) per sub-game.
- `services/artifact_models.py`/`artifact_builders.py`/`artifacts.py`/
  `series_artifacts.py` (Phase 11): the four standardized JSON artifacts,
  verified byte-identical in schema (config/log/result) to the
  independently-built Police repo's via serialized fixture comparison.
  `domain/declaration.py::PeerDeclaration` gained `to_dict()`/`validate()`
  to satisfy the artifact-save protocol.
- `services/replay_verifier.py`/`replay_loader.py`/`replay_checks.py`
  (Phase 12): independent headless replay verifier — game_uid/config-hash/
  count/duplicate-sub-game-number/step-count checks, full commitment/nonce/
  sequence audit, barrier/capture bounds, score recomputation,
  VERIFIED/TAMPERED verdict. 16 tests covering 11 tamper categories plus
  missing-log, missing-artifacts, and duplicate-record detection.
- `sdk/game_runner.py` (new) + `__main__.py`: `run-subgame`, `run-series`
  (with `--artifacts-dir`), `verify-replay`, and a new `show-status`
  command. Ctrl+C is caught at the top level and reported as a clean exit
  130, not a raw traceback.
- `services/game_ids.py` (new): `derive_game_id`/`derive_game_uid`,
  implementing `protocol_contract.md` §3.1's documented (clean-room
  reimplementable) formula.

### Fixed — Session recovery step B

- `infrastructure/server_lifecycle.py` — production HTTP shutdown still
  used raw `asyncio.Task.cancel()` after step A's test-only fix; direct
  experiment confirmed this never reaches `uvicorn.Server.shutdown()` (no
  `try/finally` around it in uvicorn's own `_serve()`), permanently leaking
  the listening socket. Rewritten around a new `ManagedServer` class
  (independent implementation): graceful `should_exit` -> bounded-timeout
  `force_exit` -> last-resort-cancel escalation, every outcome honestly
  classified. Refuses to bind to any host other than
  `127.0.0.1`/`localhost`/`::1`. `sdk/negotiation_runner.py` updated to the
  new API; the old `IntentionalShutdown`/`run_server_managed`/`stop_server`
  API removed entirely. 11 new regression tests
  (`tests/integration/test_server_lifecycle.py`). See
  `integration_lab/evidence/session_recovery_step_b/server_lifecycle/`.
- `infrastructure/mcp_client.py` — did not catch
  `fastmcp.exceptions.ToolError` (an opponent reachable but rejecting a
  call at the MCP protocol level, e.g. an unknown tool name), letting it
  crash the runtime as an unhandled exception instead of a clean
  `PeerUnavailableError` -> `TECHNICAL_LOSS`. Added to the caught
  connection-failure set; regression test added.

### Fixed — Session recovery step A

- `services/subgame_runtime.py::SubGameRuntime.run()` — a caller-supplied
  `max_turns` smaller than the configured `survival_threshold` (only
  reachable via an explicit test/caller cap, never the default production
  cap) let the turn loop exhaust without reaching a legal terminal state,
  so `_finalize()`'s `state is not ERROR` check let a `WAITING` state
  through to an illegal `BEGIN_AUDIT` transition
  (`IllegalTransitionError: no transition from waiting on begin_audit`).
  Added `SubGameRuntime.abort(reason)` as the single shared path for both
  this case and an external cancellation mid-run: it forces the state
  machine to `ERROR` (a legal transition from any non-terminal state) and
  finalizes as an explicit `TECHNICAL_LOSS` with no audit, so an
  artificially-capped or cancelled sub-game can never be reported as a
  completed, audited game. `run()` now also catches `asyncio.CancelledError`
  to call `abort()` before re-raising, so cancellation is never silently
  swallowed and the state machine always ends in a legal state. See
  `docs/ARCHITECTURE.md` ("Sub-game exit and audit transition") and
  `integration_lab/evidence/session_recovery_step_a/thief_state_fix/`.
- `services/outcomes.py` — removed `dataclasses.field`, imported but never
  used (both dataclasses use plain immutable defaults, e.g. `records:
  tuple[...] = ()`, which need no `field(default_factory=...)`). Confirmed
  no other file in the diff needed it either; `ruff check .` is clean.
- Ran `ruff format .` across both new (previously unformatted) Batch 2
  source/test files and confirmed, by diffing against the pre-session
  patch in `integration_lab/evidence/session_recovery/thief_partial.patch`,
  that the three previously-tracked files it touched
  (`infrastructure/mcp_client.py`, `sdk/negotiation_runner.py`,
  `shared/private_config.py`) came out byte-identical to their state before
  this session — i.e. `ruff format` changed nothing in them at all;
  formatting only applied to the new, previously-unformatted files.

### Added — Implementation Batch 1
- Configuration: `shared/{errors,config_sections,config_validation,config_models,
  private_config,rate_limits_model,config_loader,canonical_json}.py` — loads and
  strictly validates `game.json`/`game.toml`/`rate_limits.json`, rejects private
  overrides of shared fields, computes SHA-256 of the raw shared config.
- Domain models: `Role`, `Position`/`Direction`, `MoveAction`/`StayAction`/
  `BarrierAction`, `Hint`, `CaptureClaim`/`CaptureResponse`/`SubGameOutcome`,
  `LocalObservation`/`PublicTurnEnvelope`, `LocalPeerState` — structurally guaranteed
  to hold only this peer's own truth plus public info (tested by field introspection).
- Board physics: `domain/board.py`, `domain/rules.py` (movement, barrier legality,
  capture rules, visually verified against the book, not HW6), `domain/scoring.py`.
- Scent model: exact 5x5 emission matrix + decay formula (`domain/scent.py`).
- Belief model: normalized probabilistic belief update — prior, transition, scent
  likelihood, calibrated hint likelihood, entropy, top-k (`domain/belief_model.py`,
  `domain/belief_updates.py`); see `docs/BELIEF_MODEL.md`.
- Protocol schemas: strict validation for every message category (health,
  declaration, config proposal, ack, turn commit/reveal, public envelope, hint,
  scent payload, barrier declaration, capture claim/response, audit submission,
  control, error) — `protocol/*.py`.
- Minimal real FastMCP HTTP vertical slice: `infrastructure/mcp_server.py` (health,
  negotiate, propose_config tools), `infrastructure/mcp_client.py`,
  `sdk/negotiation_runner.py`, `__main__.py negotiate-smoke` — proven over a real
  two-independent-process HTTP handshake (not mocked).
- 100 tests, 94.43% coverage, 0 Ruff violations, all files <=150 meaningful lines.

### Not yet implemented
- Full turn-by-turn game loop, commit-reveal/audit lifecycle, strategy brains, state
  machine/DeadlineTracker/Watchdog, GUI, replay viewer, Gmail reporter, league runner.
  See `integration_lab/audit/PROGRESS.md` for the current readiness level (still
  below `LOCAL_READY`).
