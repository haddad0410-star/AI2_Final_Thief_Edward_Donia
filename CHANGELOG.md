# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

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
