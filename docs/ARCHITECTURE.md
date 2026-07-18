# Architecture — Thief Peer

Canonical protocol reference: `integration_lab/audit/protocol_contract.md`. This file
is the role-local summary; if the two ever disagree, the integration_lab audit copy
wins until reconciled.

## Component responsibilities (`src/thief_peer/`)

| Package | Responsibility | Batch 1 status |
|---|---|---|
| `sdk/` | Single public entry point; no business logic itself, delegates to the layers below | `negotiation_runner.py` implemented (minimal vertical slice orchestration only) |
| `domain/` | Board, movement/barrier rules, scoring, scent/pheromone model, belief fusion, own-state tracking — pure game logic, no I/O | Implemented: `roles`, `positions`, `actions`, `hints`, `captures`, `board`, `rules`, `scoring`, `scent`, `belief_model`, `belief_updates`, `observations`, `state` |
| `protocol/` | Wire message dataclasses (turn/control/audit), canonical JSON serialization | Schemas implemented (`envelope`, `messages_handshake`, `messages_evidence`, `messages_turn`, `messages_capture`, `messages_control`); full lifecycle wiring is a later batch |
| `strategy/` | `BaselineThiefBrain`, `EntropyEscapeThiefBrain`, shared `BrainBase`/`Decision` contract | Not started — design only, see `integration_lab/audit/strategy_proposals.md` |
| `infrastructure/` | FastMCP server/client, Gmail sender, rate limiter/Gatekeeper, transport-level concerns | `mcp_server.py`/`mcp_client.py` implemented (health/negotiate/config-hash-compare only); Gmail sender not started |
| `services/` | Cross-cutting orchestration (e.g. the peer runtime/state machine, deadline tracker, watchdog) built on top of `domain` + `protocol` + `infrastructure` | Not started |
| `gui/` | Live view + replay viewer; never displays the opponent's true position | Not started |
| `shared/` | Config loading/validation, logging setup, version info — no game logic | Implemented: `errors`, `config_sections`, `config_validation`, `config_models`, `private_config`, `rate_limits_model`, `config_loader`, `canonical_json` |

## Independence guarantees

- No import of `thief_peer` or `integration_lab` from this package.
- No shared log/config file path with the opponent process.
- No in-memory singleton shared across processes (impossible anyway — separate OS
  processes — but also never designed as if it were possible).

These are enforced by `integration_lab/verify_isolation.py`, run against both real
repositories with zero violations as of Batch 1 (`integration_lab/evidence/
verify_isolation_output.json`).

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
reported as a completed, audited game. See `integration_lab/evidence/
session_recovery_step_a/thief_state_fix/` for the bug this replaced (a bare
`state_machine.state is not ERROR` check let a WAITING state through to an
illegal `BEGIN_AUDIT`) and the regression tests added.
