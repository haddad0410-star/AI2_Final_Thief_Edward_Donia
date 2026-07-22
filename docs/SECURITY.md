# Security — Thief Peer

## Threat model summary

Full detail: `integration_lab/audit/risk_register.md` and (once written)
`reports/threat_model.md`. Core adversarial assumption per the book (Ch.5.2): the
opponent may attempt to rewrite history, deny a committed move, or lie about a
capture/win claim. Defense: SHA-256 commit-reveal (book Ch.5.3) plus a mutual
end-of-game audit that recomputes every hash.

## Secrets handling

- `credentials.json` / `token.json` live outside this repository, path supplied via
  `GOOGLE_OAUTH_CREDENTIAL_DIR` (see `.env-example`).
- `.gitignore` blocks `.env`, `credentials.json`, `token.json`, `client_secret*.json`.
- `integration_lab/security_scan.py` (implemented, Batch 1) asserts none of these are
  present/tracked, scans for API-key-like patterns, hardcoded Windows paths, reference-
  repo group identities, hardcoded paid-model-provider defaults, and a wrong
  `num_games` in the real league config. Real output (clean):
  `integration_lab/evidence/security_scan_output.json`.
- `integration_lab/verify_isolation.py` (implemented, Batch 1) asserts no cross-repo
  imports, no cross-repo config paths, no opponent-true-position field names, and no
  shared-state module hints. Real output (clean):
  `integration_lab/evidence/verify_isolation_output.json`.

## Batch 1 protocol-schema validation (implemented)

Every message category (health, declaration, config proposal, negotiation ack, turn
commitment, turn reveal, public turn envelope, hint, scent payload, barrier
declaration, capture claim/response, audit submission, control, protocol error) has
strict `__post_init__` validation and negative tests — 23 tests in
`tests/protocol/test_protocol_schemas.py`. This validates message *shape*; it does not
yet implement the commit-reveal *lifecycle* (see below).

## Planned security test categories (`tests/security/`) — later batch

- Tamper injection: alter move, hint, verdict, nonce, step, config, capture answer,
  record order — each must be detected by the audit.
- Nonce reuse rejection.
- Constant-time comparison on reveal verification (no timing side-channel).
- False capture-claim / false win-claim detection.

None of these lifecycle tests exist yet — commit-reveal is schema-only this batch
(`src/thief_peer/protocol/messages_turn.py`, `messages_capture.py`); the full sealing/
audit implementation is a later batch. This document will be updated again then.

## Session recovery step B additions

- **Production resource-leak fix**: `infrastructure/server_lifecycle.py`'s
  shutdown path previously relied on `asyncio.Task.cancel()`, which does
  not reliably close the underlying Uvicorn listening socket (verified by
  direct experiment) — a real, if low-severity, resource leak in
  production. Replaced with a `ManagedServer` class doing a genuinely
  graceful shutdown, independently implemented (no import of the Police
  repository); see the CHANGELOG and `integration_lab/evidence/
  session_recovery_step_b/server_lifecycle/`.
- **New this session (Phase 12)**: headless replay verifier
  (`services/replay_verifier.py`/`replay_loader.py`/`replay_checks.py`),
  recomputing every commitment/nonce/sequence, checking barrier/capture
  bounds, and recomputing scores/totals from the config's scoring table.
  Tested against 11 distinct tamper categories (action, hint, commitment
  hash, nonce, step number, record ordering, barrier declaration, capture
  response, config hash, result total, game_uid) plus missing-log and
  duplicate-sub-game-number detection — all detected. See
  `integration_lab/evidence/session_recovery_step_b/thief_phase_12_replay/`.
- **`infrastructure/mcp_client.py` hardening**: did not catch
  `fastmcp.exceptions.ToolError` (an opponent reachable but rejecting a
  call at the MCP protocol level), letting it crash the runtime as an
  unhandled exception instead of a clean `PeerUnavailableError` ->
  `TECHNICAL_LOSS`. Fixed; regression test added.
- Still not done: a real cross-process tamper drill against an actual
  opponent, or the mutual audit.

## Session recovery step C additions

- **Declaration schema hardened (Task 2, resolves risk #14)**: the Step-0
  declaration is now parsed via a strict allow-list (`declaration_parsing.py`
  ::`parse_declaration`) — any unrecognized top-level or `hardware` field is
  rejected outright (`SchemaValidationError`), never silently accepted.
  `declaration/1`-era aliases (`commit_hash`, `config_sha256`) are accepted
  on input only, normalized immediately, and rejected as ambiguous if
  present alongside a differing canonical value — closing a path where a
  malformed/legacy declaration could otherwise be misread. A new
  `content_sha256` commitment field (`canonical_sha256_hex` over every other
  field) gives the replay verifier an additional, independently-recomputable
  integrity check beyond the existing nonce-based seal/verify exchange
  (`declaration_checks.py`::`declaration_mismatches`). Cross-repo
  compatibility (not a security boundary by itself, but a precondition for
  any real declaration exchange) verified by
  `integration_lab/scripts/compare_declaration_schemas.py`; see
  `integration_lab/evidence/session_recovery_step_c/task2_declaration_schema/`.

## Batch 4A additions

- **Gmail credential isolation** (`infrastructure/gmail_credentials.py`):
  `credentials.json`/`token.json` resolved only via
  `GOOGLE_OAUTH_CREDENTIAL_DIR` (env var, never a config field); scope
  enforcement (`gmail.send` only, rejects `.modify`/`.compose`/`.readonly`/
  full-mailbox) happens in code before any network call; error messages
  never echo file content. 12 tests
  (`tests/security/test_gmail_credentials.py`), including a real check
  that no `credentials.json`/`token.json`/`client_secret*` file is ever
  tracked by git.
- **Gmail Gatekeeper** (`infrastructure/gmail_gatekeeper.py`): bounded
  retries (never an infinite loop), a per-attempt timeout, a queue-depth
  cap, and idempotency-key-based duplicate-send suppression — 10 tests,
  always against a mocked send function.
- **Report-refusal on unverified evidence**: the Gmail reporter runs the
  real, unmodified replay verifier on target artifacts before building
  any report and refuses (does not silently proceed) if they are not
  `VERIFIED` — `sdk/report_runner.py`, tested
  (`tests/unit/test_report_runner.py`).
- **Public-network bearer-token auth** (`infrastructure/public_auth.py`):
  env-var-only (`PUBLIC_BIND_TOKEN`) token source, constant-time
  comparison (`hmac.compare_digest`), never logged. 7 tests
  (`tests/security/test_public_auth.py`). The server's existing
  localhost-only bind guard (`infrastructure/server_lifecycle.py`) is
  unchanged — this module is prepared but not wired into the live server.
- **Live GUI opponent-position-leak scanner**
  (`tests/unit/test_gui_no_opponent_leak.py`): reflection-based, fails
  the build if any GUI-reachable dataclass grows a field shaped like
  `opponent_true_position`.
- **Replay-viewer cross-schema finding**: this repo's own replay verifier
  cannot correctly recompute the opponent's differently-shaped commitment
  hashes — see `docs/LIMITATIONS.md`'s Batch 4A section for the full
  explanation and fix (never claim a verdict this repo cannot actually
  compute).

## Batch 4B additions — bilateral commitment verification (resolves the
## Batch 4A cross-schema finding above)

- **Root cause, precisely identified**: the Batch 4A finding traced to two
  narrow, mechanical field-shape divergences, not an inherent consequence
  of independent implementation — this repo's `state` field was an opaque
  digest string (`"pos=R,C;visited=N"`) that Police's verifier could never
  parse as a position, while this repo's `config_sha256` was already a
  genuine top-level field (Police's was nested inside its own `state`
  dict). 14 of ~16 payload fields already had identical shape. Both repos'
  canonical-JSON encoders were already byte-identical. Full field-by-field
  audit: `integration_lab/evidence/batch4b/commitment_schema_audit.md`.
- **Canonical schema unified** (`domain/sealing/payload.py`,
  `CURRENT_SCHEMA_VERSION = "commitment/1"`): `state` replaced by a flat
  `position` tuple field (dropping the `visited` counter that was
  previously folded into the digest string — a deliberate simplification,
  since `visited` was never itself part of the protocol's binding field
  set). `CANONICAL_FIELD_SET` (17 keys) is now identical in both repos.
  `to_canonical_dict()` is schema-version-aware — legacy
  `sealed-turn/1`/`/2` records still canonicalize to their EXACT original
  shape (via a `legacy_state` passthrough field that preserves the real
  original `visited` count verbatim, since it is per-step state this
  dataclass no longer tracks and cannot re-derive), so all Batch 1-4A
  evidence remains self-verifiable without rewriting any file on disk.
- **Real bilateral verification, not just a shared schema on paper**:
  because the field SET is now unified, this repo's EXISTING,
  already-tested verification pipeline (`services/replay_verifier.py`,
  `replay_checks.py`) correctly recomputes and verifies a genuine Police
  `commitment/1` record too — confirmed by 10 byte-identical cross-repo
  test vectors (`integration_lab/evidence/batch4b/test_vectors/`), a
  21-category bilateral tamper matrix where BOTH repos' own verifiers
  independently detect every mutation
  (`integration_lab/evidence/batch4b/tamper_matrix/`, `all_detected=true`),
  and a real six-sub-game two-process FastMCP series where both sides'
  `replay` command reports `FULL_BILATERAL_VERIFICATION=true`
  (`integration_lab/evidence/batch4b/bilateral_series/`). This repo never
  imports `police_peer`; it only calls its own crypto/verifier on
  whichever directory it's given (`services/bilateral_verify.py`).
- **New role-consistency and unknown-field checks**
  (`replay_checks.py::_check_role_fields`/`_check_unknown_fields`): a
  Thief record carrying a Police-only `barrier_placed`/`capture_claim`
  value (or vice versa), or any `commitment/1` record carrying a field
  outside the canonical set, is now flagged as tampered — closing a class
  of forgery the schema-shape fix alone would not have caught.
- **Gmail bilateral gate** (`sdk/report_runner.py`, Task 9): `report
  --opponent-artifacts-dir <dir>` gates report construction (dry-run AND
  `--send`) on full bilateral verification via
  `services/bilateral_verify.py`, not merely this side's own
  `verify_replay`. Real evidence, both accept and refuse paths:
  `integration_lab/evidence/batch4b/gmail_bilateral_gate/`.
