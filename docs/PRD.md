# PRD — Thief Peer

## Purpose

Define what this repository must deliver for the final project: an independent
Thief peer that plays Distributed Cops-and-Robbers over FastMCP against
another group's peer, per the binding rules in
`_post4b_supplementary_evidence/audit/binding_parameters.json`.

## Scope

In scope: FastMCP server+client, local game state/physics, scent/belief model,
`BaselineThiefBrain` + `EntropyEscapeThiefBrain` strategies, SHA-256 commit-reveal,
live GUI + replay viewer, Gmail reporting (`gmail.send` only), the four JSON artifacts.

Out of scope: anything about the Police peer's internals (separate
repo), a central referee/orchestrator holding both true positions, LLM-selected moves.

## Sub-PRDs

See `PRD_fastmcp_peer.md`, `PRD_game_rules.md`, `PRD_scent_belief.md`,
`PRD_strategy.md`, `PRD_commit_reveal.md`, `PRD_gui_replay.md`,
`PRD_gmail_reporter.md` for per-area detail.

## Measurable acceptance criteria (project-level)

- [x] Two real, separate FastMCP HTTP processes (this peer + the opponent's) complete
      at least one full sub-game locally (`LOCAL_READY`).
- [x] `verify_shared_config.py`-style byte/hash comparison passes on the shared
      `game.json` between both peers.
- [x] `uv run pytest --cov=src --cov-fail-under=85` passes with zero Ruff violations.
- [x] Every submitted `.py` file is <=150 meaningful lines.
- [x] Replay viewer reports `VERIFIED`, not `TAMPERED`, on an untampered log.
- [x] A tampered log is correctly reported as `TAMPERED` (security test).
- [x] `num_games=6` in the shared league config; `num_games=1` exists only in a
      local development-only fixture (not included in this single-repo package).

All of the above are satisfied at `LOCAL_READY`. `NETWORK_READY`/`LEAGUE_READY`/
`SUBMISSION_READY` are not claimed — those depend on the still-open manual gates
(public endpoint, real league opponent, Gmail OAuth send, NotebookLM export,
repository visibility, GitHub push). Status tracked in
`_post4b_supplementary_evidence/audit/PROGRESS.md` and
`_post4b_supplementary_evidence/post4b_finalization/FINAL_LOCAL_AUDIT.md`.
