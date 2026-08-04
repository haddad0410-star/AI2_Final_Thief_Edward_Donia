# TODO — Thief Peer

| Phase | Task | Owner | Status | Dependency | Definition of Done | Evidence |
|---|---|---|---|---|---|---|
| 0 | Extract binding parameters, protocol contract, reuse plan, manual gates, risk register, strategy proposals, visual verification | Claude | DONE | — | Files exist with substantive content | `_post4b_supplementary_evidence/audit/*` |
| 1 | Create this repo's directory skeleton, git init | Claude | DONE | Phase 0 | Repo exists, `git init` run, no remote | `git -C thief_peer log`, `git -C thief_peer status` |
| 2 | Documentation skeletons, ADRs, config drafts | Claude | DONE | Phase 1 | All listed files exist with real content, not empty stubs | this file tree |
| 3 | Shared constitution: `game.json`/`game.toml`/`rate_limits.json` loaders + validation, `verify_shared_config.py` passes | Claude | DONE (Batch 1) | Phase 2 | Hash match printed for both peers' `game.json`; loaders reject invalid/missing/override configs | `verify_shared_config.py` output (a workspace-only script, run during development in the full multi-repo workspace, not included in this single-repo package), `tests/unit/test_shared_config.py`, `test_private_config.py`, `test_rate_limits_config.py` (26 tests) |
| 4 (partial) | Minimal FastMCP server+client vertical slice: health/negotiate/config-hash-compare/ack/shutdown | Claude | DONE (Batch 1, vertical slice only) | Phase 3 | Real two-process HTTP round-trip succeeds | negotiation-smoke raw evidence (produced during development, not included in this package), `tests/integration/test_mcp_negotiation.py` (7 tests), `test_negotiation_runner.py` (2 tests) |
| 4 (remainder) | Full game-loop protocol (turn commit/reveal/audit lifecycle) | Claude | DONE | Batch 1 slice | Real HTTP round-trip carries actual turns | `tests/integration/`, real bilateral series evidence: `_post4b_supplementary_evidence/batch4b/bilateral_series/` |
| 5 | Game state/physics (board, rules, barriers, scoring) | Claude | DONE (Batch 1) | Phase 3 | Unit tests green | `tests/unit/test_rules.py` (15 tests), `test_scoring.py` (4 tests) |
| 6 | Scent + belief model | Claude | DONE (Batch 1) | Phase 4-5 | Belief sums to 1, no true-position leak | `tests/unit/test_scent.py` (10), `test_belief.py` (13), `docs/BELIEF_MODEL.md`, scent/belief reference-run evidence (produced during development, not included in this package) |
| 7 | `BaselineThiefBrain` + `EntropyEscapeThiefBrain`, experiments | Claude | DONE — both implemented, tested, and used in real gameplay (`config/thief_advanced/game.toml` wires `EntropyEscapeThiefBrain`; `config/thief/game.toml` defaults to `BaselineThiefBrain`); see `_post4b_supplementary_evidence/audit/strategy_proposals.md` for the pre-registered evaluation methodology | Phase 5-6 | Raw CSV/JSON results, no unsupported claims | `tests/unit/` strategy tests, `src/thief_peer/strategy/`, `docs/STRATEGY.md` |
| 8 | SHA-256 commit-reveal + mutual audit (full lifecycle) | Claude | DONE | Phase 4 | Tamper tests all detected | `tests/security/`, `_post4b_supplementary_evidence/batch4b/tamper_matrix/` |
| 9 | State machine, DeadlineTracker, Watchdog | Claude | DONE | Phase 4 | Failure drills pass | `tests/integration/`, `src/thief_peer/domain/deadline.py`, `src/thief_peer/domain/watchdog.py` |
| 9b | Protocol message schemas (health/declaration/config-proposal/ack/commit/reveal/hint/scent/barrier/capture/audit/control/error) -- validation only, no lifecycle wiring yet | Claude | DONE (Batch 1) | Phase 4 | Strict validation + negative tests for every category | `tests/protocol/test_protocol_schemas.py` (23 tests), `docs/adr/ADR-0012-receive-move-alias-assessment.md` |
| 10 | Live GUI + replay viewer | Claude | DONE (Batch 4A) | Phase 5-8 | Replay shows VERIFIED on untampered log | manual screenshot per `screenshots/README.md`, `src/thief_peer/gui/`, `_post4b_supplementary_evidence/batch4b/graphical_replay_regression/` |
| 11 | Four JSON artifacts + schema validation | Claude | DONE | Phase 4,8 | Schema tests pass, negative tests too | `tests/protocol/`, `src/thief_peer/services/artifact_models.py`/`artifact_builders.py`/`artifacts.py`/`series_artifacts.py` |
| 12 | Gmail reporting (`gmail.send` only, dry-run default) | Claude | DONE (dry-run default; `--send` exists in code but has never been invoked, gated behind Manual Gate C) | Manual Gate C | Dry-run JSON produced, no real send without `--send` + your approval | `_post4b_supplementary_evidence/batch4a_gmail_dry_run/` |
| 13 | Quality gates: coverage >=85%, Ruff clean, file-length check | Claude | DONE, full current codebase (real, tested, passing — 468 tests passed / 0 failed, ~92% coverage, 0 Ruff violations, all `src/` files <=150 lines, per the most recent full-repo audit) | all modules | CI green | `_post4b_supplementary_evidence/post4b_finalization/FINAL_LOCAL_AUDIT.md`, `reports/batch1_quality_output.txt` (Batch 1 only, superseded) |
| 14 | Two-process local integration series | Claude | DONE — real bilateral series run repeatedly over real localhost FastMCP, including a real independent bilateral result-agreement exchange (both peers verify matching totals) | Phase 4-13 | Full 6-sub-game series locally | `_post4b_supplementary_evidence/batch4b/bilateral_series/` |
| 15 | Public network + league (manual gates) | You | NOT STARTED | Manual Gates A, B | Real remote match | league evidence bundle |
| 16 | Academic report finalized | Claude | DONE — `README.md` is complete and reflects real, current `LOCAL_READY` status with no inflated readiness claim | Phase 7,14 | README complete with real data | this README |
| 17 | Git tag + push (manual approval) | You | NOT STARTED | all above | `v1.0-submission` tag, pushed | `git log --tags` |
| 18 | Final audit + clean packaging | Claude | DONE | Phase 17 | ZIP validated | `_post4b_supplementary_evidence/post4b_finalization/FINAL_LOCAL_AUDIT.md` |

Do not mark a task DONE before its evidence file exists — see `CLAUDE.md`'s
no-fabricated-evidence rule.

## Session recovery step C (this session)

Resolved the declaration schema divergence (risk #14, canonical
`declaration/2`); verified all four artifact contracts compatible; ran a
real FastMCP lifecycle regression (3x); ran a REAL one-sub-game two-process
HTTP game (Phase 4/14 in the table above, first real cross-process game);
ran a real six-sub-game two-process HTTP series (Phase 14); ran the mutual
cross-repo audit (96/96 checks passed); ran 18 bounded failure drills (Phase
9); ran full quality/security/reproducibility gates (Phase 13). Six real
cross-repo protocol defects found and fixed only by actually running two
independent processes — see `CHANGELOG.md` and
`_post4b_supplementary_evidence/audit/risk_register.md` risks #15-#16. Phases 4 (remainder),
9, 11, 13, 14 in the table above should now be read as DONE per this step's
evidence (`session_recovery_step_c/`, a development-workspace artifact under
the full project workspace's `integration_lab/evidence/`, not included in
this standalone package); the table
itself predates Batch 2/step C numbering — treat `PROGRESS.md` as the
current source of truth. Readiness: `LOCAL_READY`.

## Session recovery step A (this session)

The Batch 2 background agent for this repo was killed mid-run by
infrastructure failures (not task-logic failures) with a large amount of
uncommitted Phase 3-9-range work in progress — but explicitly **without**
Phases 10-12 (series runtime, artifact generator, replay verifier) or the
`run-subgame`/`run-series`/`verify-replay` CLI wiring, none of which existed in
this repo at that point in history (see `session_recovery/recovery_notes.md`,
a development-workspace artifact under the full project workspace's
`integration_lab/evidence/`, not included in this standalone package). This
recovery step fixed only the one specific bug that
agent was mid-fix on (an illegal `WAITING -> BEGIN_AUDIT` state transition
when a caller-supplied turn cap is smaller than the configured
`survival_threshold` — see `session_recovery_step_a/thief_state_fix/`, same
development-workspace evidence tree) plus a Ruff unused-import fix and
quality gates; it did not implement Phases 10-12, run a real two-process
series, or advance readiness past `LOCAL_READY`. The phase table above still
reflects Batch 1 status only and has not been re-audited phase-by-phase
against the uncommitted Batch 2 work in this recovery step — that re-audit,
plus Phases 10-12, is Recovery Step B+ work, not this step.

## Session recovery step B (this session)

Implemented Phases 10-12 and CLI wiring from scratch (independent
implementation, no import of the Police repository): `services/
series_runtime.py` (Phase 10), `services/artifact_models.py`/
`artifact_builders.py`/`artifacts.py`/`series_artifacts.py` (Phase 11),
`services/replay_verifier.py`/`replay_loader.py`/`replay_checks.py` (Phase
12), and `sdk/game_runner.py` + `run-subgame`/`run-series`/`verify-replay`/
`show-status` in `__main__.py`. Also fixed the production FastMCP/Uvicorn
shutdown defect (see `CHANGELOG.md`) and hardened `mcp_client.py` against
`ToolError`. Thief grew from 220 tests (step A checkpoint) to 281 tests,
94.79% coverage. Full detail: `session_recovery_step_b/`, a
development-workspace artifact under the full project workspace's
`integration_lab/evidence/`, not included in this standalone package. At
that point in history, still NOT implemented or run: a real
two-process series with an actual Police opponent, the mutual cross-repo
audit, GUI, replay viewer (Phase 10 in the table above), Gmail (Phase 12 in
the table above), public network/league play (Phase 15), or advanced
strategy (`EntropyEscapeThiefBrain`, Phase 7) — all of these are now DONE,
per the phase table above. The phase table's numbering
above predates Batch 2 and does not line up 1:1 with the Batch-2 phase
numbers used in `_post4b_supplementary_evidence/audit/PROGRESS.md` and the CHANGELOG —
treat the table above as historical (Batch 1) and the CHANGELOG +
PROGRESS.md as the current source of truth for Batch 2 status.

## Implementation Batch 4A (this session)

GUI (Phase 10 in the table above), replay viewer, and Gmail reporting
(Phase 12) are now **DONE** (dry-run only for Gmail — real send gated
behind Manual Gate C, never invoked). Public network/league play (Phase
15) remains preparation-only (Manual Gates A/B). See `CHANGELOG.md` and
`_post4b_supplementary_evidence/audit/PROGRESS.md` for full detail. The
table above has since been updated (post-Batch-4B audit pass) to mark
Phases 4 (remainder), 7, 8, 9, 10, 11, 12, and 14 **DONE** to match real,
current implementation status — it no longer needs to be read as
Batch-1-only or historical.
