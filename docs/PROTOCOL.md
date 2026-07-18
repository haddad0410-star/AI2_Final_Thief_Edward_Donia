# Protocol — Thief Peer (role-local summary)

**Canonical source:** `integration_lab/audit/protocol_contract.md`. This file
summarizes only what's specific to running this repo as the Thief side.

- This peer's default local port: `8902` (private, set in `config/thief/game.toml`, not negotiated).
- Opponent URL: supplied via this peer's own `game.toml` / `.env` (`OPPONENT_MCP_URL`) —
  the only network detail this peer is given about the opponent.
- Tool surface exposed by this peer's FastMCP server: `negotiate`, `receive_turn`,
  `submit_audit`, `receive_control` (see canonical doc for exact schemas). **Batch 1
  implements only `health`, `negotiate`, and `propose_config`** (real HTTP, see
  `src/thief_peer/infrastructure/mcp_server.py`) — `receive_turn`/`submit_audit`/
  `receive_control` are schemas only (`src/thief_peer/protocol/`), not yet wired to
  server tools; that is a later batch. See `docs/adr/ADR-0012-receive-move-alias-
  assessment.md` for the `receive_move` alias decision.
- Thief-specific wire fields: `claim_response` (this side must answer honestly), `win_claim` (this side sends it on survival).
- Four JSON artifacts this peer writes each series: `declaration_<game_id>.json`,
  `config_<game_id>_g<NN>.json` (x6), `log_<game_id>_g<NN>.json` (x6),
  `result_<game_id>.json`. Implemented (session recovery step B, Phase 11)
  and wired into `run-series --artifacts-dir`; verified byte-identical in
  schema (config/log/result) to the independently-built Police repo's
  artifacts via serialized fixture comparison. The Step-0 declaration
  schema is now frozen and cross-repo-compatible as canonical
  `declaration/2` (session recovery step C, Task 2 — see
  `docs/schemas/declaration.schema.json`,
  `integration_lab/audit/protocol_contract.md` §3.4a, and
  `integration_lab/audit/risk_register.md` risk #14, now resolved).
- Real two-process negotiation evidence: `integration_lab/evidence/negotiation_smoke/`
  (actual stdout/stderr/exit codes from two independently-launched OS processes).
  A real two-process full game/series has NOT been run yet (explicitly out
  of scope through session recovery step B).
- Sub-game lifecycle (Batch 2): `submit_audit`'s local counterpart,
  `BEGIN_AUDIT`, is only ever driven from `SUB_GAME_OVER` — a real capture or
  survival outcome. A protocol error, a caller-supplied turn cap smaller than
  `survival_threshold`, or an external cancellation all route through `ERROR`
  instead (`SubGameRuntime.abort()`), so this peer can never submit an audit
  for a sub-game it did not actually finish. See `docs/ARCHITECTURE.md`
  ("Sub-game exit and audit transition") for the full state table.
