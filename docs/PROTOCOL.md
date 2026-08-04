# Protocol — Thief Peer (role-local summary)

**Canonical source:** `_post4b_supplementary_evidence/audit/protocol_contract.md`. This file
summarizes only what's specific to running this repo as the Thief side.

- This peer's default local port: `8902` (private, set in `config/thief/game.toml`, not negotiated).
- Opponent URL: supplied via this peer's own `game.toml` / `.env` (`OPPONENT_MCP_URL`) —
  the only network detail this peer is given about the opponent.
- Tool surface exposed by this peer's FastMCP server: `negotiate`, `receive_turn`
  (plus its `receive_move` alias), `submit_audit`, `receive_control` (see canonical
  doc for exact schemas). **Batch 1 implemented only `health`, `negotiate`, and
  `propose_config`** (real HTTP, see `src/thief_peer/infrastructure/mcp_server.py`);
  `receive_turn`/`submit_audit`/`receive_control` were schemas-only at that point.
  All four tools are now fully implemented and wired through
  `infrastructure/game_tools.py` and `infrastructure/turn_router.py`, used in real
  two-process gameplay. See `docs/adr/ADR-0012-receive-move-alias-
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
  `_post4b_supplementary_evidence/audit/protocol_contract.md` §3.4a, and
  `_post4b_supplementary_evidence/audit/risk_register.md` risk #14, now resolved).
- Real two-process negotiation evidence (actual stdout/stderr/exit codes
  from two independently-launched OS processes) was captured during
  development in the full project workspace; not included in this
  single-repo package.
  A real two-process full game/series has NOT been run yet (explicitly out
  of scope through session recovery step B).
- Sub-game lifecycle (Batch 2): `submit_audit`'s local counterpart,
  `BEGIN_AUDIT`, is only ever driven from `SUB_GAME_OVER` — a real capture or
  survival outcome. A protocol error, a caller-supplied turn cap smaller than
  `survival_threshold`, or an external cancellation all route through `ERROR`
  instead (`SubGameRuntime.abort()`), so this peer can never submit an audit
  for a sub-game it did not actually finish. See `docs/ARCHITECTURE.md`
  ("Sub-game exit and audit transition") for the full state table.

**Note (this section describes Batch-1-era scope; the peer has since grown
`receive_turn`/`submit_audit` and real multi-process series validation —
see `_post4b_supplementary_evidence/audit/PROGRESS.md` for current status.)**

**Scent field-name correction (Batch 3.6 Task 2):** `protocol_contract.md`
§3.2's `scent_grid` field name is this project's own paraphrase of the
book's prose description of the sealed record — a full-text search of the
book PDF found no literal `scent_grid`/`smell_grid` field name anywhere.
The underlying semantics (full-board cumulative decaying trail, sealed raw
values not a digest) are still correctly implemented; only the exact
identifier is ours (full book-citation audit produced during development
in the full project workspace; not included in this single-repo package).

**Sealed-record schema unified as `commitment/1` (Batch 4B):** the sealed
turn payload's field set is now identical in both repos (17 canonical
fields, `domain/sealing/payload.py::CANONICAL_FIELD_SET`), replacing the
prior per-repo `sealed-turn/2`/`commit-reveal/2` shapes that diverged in
two mechanical ways (this repo's opaque `state` digest string vs. the
opponent's nested dict; `config_sha256` placement). This is what makes
genuine bilateral commitment verification possible — see
`_post4b_supplementary_evidence/batch4b/commitment_schema_audit.md` and
`docs/SECURITY.md`'s Batch 4B section. `protocol_contract.md` should be
updated to reference `commitment/1` as the current binding sealed-record
schema once both groups' contract is renegotiated with a real opponent;
until then this is a same-project-internal schema unification, not yet a
cross-team-negotiated protocol change.
