# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

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
