# Architecture — Thief Peer

Canonical protocol reference: `_post4b_supplementary_evidence/audit/protocol_contract.md`.
This file is the role-local summary; if the two ever disagree, the audit copy wins
until reconciled.

## Component responsibilities (`src/thief_peer/`)

All packages below are implemented and covered by the real, passing test suite
(`LOCAL_READY`); the table records what each package contains, not an
in-progress/not-started distinction.

| Package | Responsibility | Status |
|---|---|---|
| `sdk/` | Single public entry point; no business logic itself, delegates to the layers below | Implemented: `negotiation_runner.py` plus the full `game_runner.py` facade wiring config loading, this peer's server, the HTTP opponent gateway, and the sub-game/series runtimes |
| `domain/` | Board, movement/barrier rules, scoring, scent/pheromone model, belief fusion, own-state tracking, state machine, deadline tracker, watchdog — pure game logic, no I/O | Implemented: `roles`, `positions`, `actions`, `hints`, `captures`, `board`, `rules`, `scoring`, `scent`, `belief_model`, `belief_updates`, `observations`, `state`, `state_machine/`, `deadline.py`, `watchdog.py` |
| `protocol/` | Wire message dataclasses (turn/control/audit), canonical JSON serialization | Implemented: schemas (`envelope`, `messages_handshake`, `messages_evidence`, `messages_turn`, `messages_capture`, `messages_control`) with full lifecycle wiring through `infrastructure/game_tools.py` and `infrastructure/turn_router.py` |
| `strategy/` | `BaselineThiefBrain`, `EntropyEscapeThiefBrain`, shared `BrainBase`/`Decision` contract | Implemented, tested, and used in real gameplay — `config/thief/game.toml` defaults to `BaselineThiefBrain`; `config/thief_advanced/game.toml` wires `EntropyEscapeThiefBrain`. Neither is claimed superior on survival rate; see `docs/STRATEGY.md` and `_post4b_supplementary_evidence/audit/strategy_proposals.md` |
| `infrastructure/` | FastMCP server/client, Gmail sender, rate limiter/Gatekeeper, transport-level concerns | Implemented: `mcp_server.py`/`mcp_client.py` expose the full tool surface (`negotiate`, `receive_turn`/`receive_move` alias, `submit_audit`, `receive_control`); Gmail sender implemented, dry-run by default, real send gated behind Manual Gate C and never invoked |
| `services/` | Cross-cutting orchestration (peer runtime/state machine glue, sub-game/series runtime, artifact builders, replay verifier) built on top of `domain` + `protocol` + `infrastructure` | Implemented: `series_runtime.py`, `artifact_models.py`/`artifact_builders.py`/`artifacts.py`/`series_artifacts.py`, `replay_verifier.py`/`replay_loader.py`/`replay_checks.py` |
| `gui/` | Live view + replay viewer; never displays the opponent's true position | Implemented (Batch 4A): `view_model.py`/`event_queue.py`/`background_runner.py` (pure/headless), `tk_app.py`/`tk_board.py`/`tk_panels.py` (live Tkinter rendering), `replay_view_model.py`/`replay_steps.py`/`replay_playback.py` (pure/headless), `tk_replay_app.py`/`tk_replay_board.py`/`tk_replay_panels.py` (replay Tkinter rendering) |
| `shared/` | Config loading/validation, logging setup, version info — no game logic | Implemented: `errors`, `config_sections`, `config_validation`, `config_models`, `private_config`, `rate_limits_model`, `config_loader`, `canonical_json` |

## Independence guarantees

- No import of `thief_peer` or `integration_lab` from this package.
- No shared log/config file path with the opponent process.
- No in-memory singleton shared across processes (impossible anyway — separate OS
  processes — but also never designed as if it were possible).

These are enforced by `verify_isolation.py`, a workspace-only script run against both
real repositories during development (not included in this single-repo package);
the FINAL_LOCAL_AUDIT re-confirms `"isolated": true`, zero violations, both repos
(`_post4b_supplementary_evidence/post4b_finalization/FINAL_LOCAL_AUDIT.md`).

## State machine

See `docs/PLAN.md`. Batch 1 proved only the two-process FastMCP HTTP handshake;
the full turn-by-turn state machine (`domain/state_machine/`) and the sub-game
runtime that drives it (`services/subgame_runtime.py`) were added in Batch 2.

### Sub-game exit and audit transition (Batch 2, session recovery step A)

`BEGIN_AUDIT` is legal from exactly one state: `SUB_GAME_OVER` (reached only via
`VERIFYING --SUB_GAME_ENDED--> SUB_GAME_OVER`, i.e. a real capture or a real
survival-threshold outcome). `SubGameRuntime._finalize()` only runs the audit
when the machine is not in `ERROR`, so every non-`SUB_GAME_OVER` exit must reach
`ERROR` first — never `BEGIN_AUDIT` from anywhere else.

`SubGameRuntime.run()` has exactly one legal exit for each way a sub-game can
stop:

| How it stops | State-machine path | Result | Audited? |
|---|---|---|---|
| Capture | `VERIFYING -> SUB_GAME_OVER -> AUDITING` | `CAPTURE` | Yes |
| Survival threshold reached | `VERIFYING -> SUB_GAME_OVER -> AUDITING` | `SURVIVAL` | Yes |
| Protocol error (opponent malformed/unreachable) | any non-terminal state `-> ERROR` (`run_turn`'s own handler) | `TECHNICAL_LOSS` | No |
| A caller-supplied `max_turns` smaller than what `survival_threshold` needs (test/local cap only — unreachable with the default, production cap) | `SubGameRuntime.abort()` forces `-> ERROR` | `TECHNICAL_LOSS` | No |
| External cancellation (deadline/watchdog abort while `WAITING`, `THINKING`, or mid-turn) | `SubGameRuntime.abort()` forces `-> ERROR`, then the `CancelledError` is re-raised (never swallowed) | `TECHNICAL_LOSS` (recorded on the runtime; the coroutine itself does not return a value) | No |

`SubGameRuntime.abort(reason)` is the single shared mechanism for the last two
rows: it forces `ERROR` (if not already there) and finalizes as an explicit
`TECHNICAL_LOSS`, so an artificially-capped or cancelled sub-game can never be
reported as a completed, audited game. The bug this replaced (a bare
`state_machine.state is not ERROR` check that let a WAITING state through to an
illegal `BEGIN_AUDIT`) and its fix were captured in session-recovery evidence
produced during development (not included in this single-repo package); the
regression tests added for it remain in `tests/`.

## Series runtime, artifacts, replay verifier, CLI (session recovery step B)

`services/series_runtime.py::run_series()` reuses `SubGameRuntime`, passing
one shared `PeerStateMachine` across all sub-games (`machine` parameter,
also new this session) so this peer's own incoming-message server
(`infrastructure/game_tools.py::build_game_server`, which validates
messages against that same machine) and the local turn loop stay in sync.
Sub-game 1 bootstraps the full `SERVER_STARTED..SUB_GAME_START` sequence;
sub-game 2+ starts already at `WAITING` (reached by the previous
sub-game's `AUDITING -> NEXT_SUB_GAME` transition) via
`SubGameRuntime.run(bootstrap=False)`. A technical loss (`ERROR`) ends the
series immediately, matching the single-sub-game contract above.

`services/artifact_models.py`/`artifact_builders.py`/`artifacts.py`/
`series_artifacts.py` (Phase 11) and `services/replay_verifier.py`/
`replay_loader.py`/`replay_checks.py` (Phase 12) are independent
implementations (no import of the Police repository) verified
schema-compatible with Police's equivalents via serialized fixture
comparison (feature-parity evidence produced during development, not
included in this single-repo package). `sdk/game_runner.py` wires config loading, this peer's
server, the HTTP opponent gateway, and these runtimes into
`run_subgame_headless`/`run_series_headless`, called from `__main__.py`'s
`run-subgame`/`run-series` (with `--artifacts-dir`) commands. **The live
cross-process path is validated for real and repeatedly re-run since** (a
real one-sub-game and real six-sub-game two-process series against the
Police repo, both over real FastMCP HTTP, most recently including the real
bilateral result-agreement exchange) — see
`_post4b_supplementary_evidence/batch4b/bilateral_series/` and `docs/LIMITATIONS.md`.
