# Security — Thief Peer

## Threat model summary

Full detail: `_post4b_supplementary_evidence/audit/risk_register.md` and (once written)
`reports/threat_model.md`. Core adversarial assumption per the book (Ch.5.2): the
opponent may attempt to rewrite history, deny a committed move, or lie about a
capture/win claim. Defense: SHA-256 commit-reveal (book Ch.5.3) plus a mutual
end-of-game audit that recomputes every hash.

## Secrets handling

- `credentials.json` / `token.json` live outside this repository, path supplied via
  `GOOGLE_OAUTH_CREDENTIAL_DIR` (see `.env-example`).
- `.gitignore` blocks `.env`, `credentials.json`, `token.json`, `client_secret*.json`.
- `security_scan.py` (implemented, Batch 1; part of the full multi-repo
  project workspace tooling, not shipped in this single-repo package)
  asserts none of these are present/tracked, scans for API-key-like
  patterns, hardcoded Windows paths, reference-repo group identities,
  hardcoded paid-model-provider defaults, and a wrong `num_games` in the
  real league config. Real output was clean, recorded during development
  in the full project workspace (not included in this single-repo
  package).
- `verify_isolation.py` (implemented, Batch 1; same full-workspace
  tooling as above) asserts no cross-repo imports, no cross-repo config
  paths, no opponent-true-position field names, and no shared-state
  module hints. Real output was clean, recorded during development in
  the full project workspace (not included in this single-repo package).

## Batch 1 protocol-schema validation (implemented)

Every message category (health, declaration, config proposal, negotiation ack, turn
commitment, turn reveal, public turn envelope, hint, scent payload, barrier
declaration, capture claim/response, audit submission, control, protocol error) has
strict `__post_init__` validation and negative tests — 23 tests in
`tests/protocol/test_protocol_schemas.py`. This validated message *shape* only at
Batch 1; the commit-reveal *lifecycle* itself is implemented and tested, see below.

## Security test categories (`tests/security/`) — implemented

- Tamper injection: alter move, hint, verdict, nonce, step, config, capture answer,
  record order — each is detected by the audit (`tests/security/test_tamper.py`, 13
  single-field mutation cases plus record-order/gap detection).
- Nonce reuse rejection — `tests/unit/test_sealing.py::test_nonce_reuse_is_detected`.
- Constant-time comparison on reveal verification (`secrets.compare_digest`, no
  timing side-channel) — verified via monkeypatch spy in `tests/unit/test_sealing.py`.
- False capture-claim / false win-claim detection — covered by the tamper-injection
  cases above plus `tests/unit/test_capture_response_delay.py`.

The full sealing/audit implementation (`src/thief_peer/domain/sealing/`) is
implemented and unified under the versioned `commitment/1` schema (Batch 4B) for
bilateral verification against the independently-built Police peer — see the
Batch 4B section below.

## Session recovery step B additions

- **Production resource-leak fix**: `infrastructure/server_lifecycle.py`'s
  shutdown path previously relied on `asyncio.Task.cancel()`, which does
  not reliably close the underlying Uvicorn listening socket (verified by
  direct experiment) — a real, if low-severity, resource leak in
  production. Replaced with a `ManagedServer` class doing a genuinely
  graceful shutdown, independently implemented (no import of the Police
  repository); see the CHANGELOG (full evidence produced during
  development in the full project workspace; not included in this
  single-repo package).
- **New this session (Phase 12)**: headless replay verifier
  (`services/replay_verifier.py`/`replay_loader.py`/`replay_checks.py`),
  recomputing every commitment/nonce/sequence, checking barrier/capture
  bounds, and recomputing scores/totals from the config's scoring table.
  Tested against 11 distinct tamper categories (action, hint, commitment
  hash, nonce, step number, record ordering, barrier declaration, capture
  response, config hash, result total, game_uid) plus missing-log and
  duplicate-sub-game-number detection — all detected (full evidence
  produced during development in the full project workspace; not
  included in this single-repo package).
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
  any real declaration exchange) verified by `compare_declaration_schemas.py`
  (part of the full multi-repo project workspace tooling, not shipped in
  this single-repo package); full evidence was likewise produced during
  development in that workspace and is not included in this single-repo
  package.

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
  audit: `_post4b_supplementary_evidence/batch4b/commitment_schema_audit.md`.
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
  test vectors (`_post4b_supplementary_evidence/batch4b/test_vectors/`), a
  21-category bilateral tamper matrix where BOTH repos' own verifiers
  independently detect every mutation
  (`_post4b_supplementary_evidence/batch4b/tamper_matrix/`, `all_detected=true`),
  and a real six-sub-game two-process FastMCP series where both sides'
  `replay` command reports `FULL_BILATERAL_VERIFICATION=true`
  (`_post4b_supplementary_evidence/batch4b/bilateral_series/`). This repo never
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
  `_post4b_supplementary_evidence/batch4b/gmail_bilateral_gate/`.

## Post-Batch-4B additions — narrow `McpError` connectivity classification

- **`infrastructure/mcp_client.py`**: a client-side session-initialize
  timeout (raised by the installed `mcp`/`fastmcp` packages as `McpError`)
  is now reclassified as `PeerUnavailableError` — but ONLY when
  `error.code == httpx.codes.REQUEST_TIMEOUT`, the exact code used by the
  only 2 client-side-timeout raise sites in the installed packages
  (verified directly against `mcp/shared/session.py` and
  `fastmcp/utilities/exceptions.py` before writing the fix). Every other
  `McpError` — a genuine remote/application error, including the
  opponent's own real JSON-RPC error forwarded verbatim — still
  propagates unchanged; this is deliberately NOT a blanket
  `except McpError`/`except Exception`. `tests/unit/test_mcp_client.py`
  proves both the narrow reclassification and that non-timeout errors are
  never swallowed.

## Gate A1 additions — local public-endpoint auth + rate-limit implementation

- **`infrastructure/auth_middleware.py`**: `BearerAuthMiddleware`, a raw
  ASGI middleware enforcing `Authorization: Bearer <PUBLIC_BIND_TOKEN>` on
  every HTTP request, applied via `FastMCP.http_app(middleware=...)` --
  before FastMCP's own routing/tool dispatch, never inside an individual
  `@mcp.tool` (so a rejected request can never invoke one). Constant-time
  comparison (`hmac.compare_digest`, verified by
  `tests/unit/test_auth_middleware_constant_time.py` spying on the real
  call, not a timing measurement). The rejection reason is one of a fixed
  small set of words -- never the presented or expected token, in the
  response, an exception, or anywhere else
  (`tests/unit/test_auth_middleware.py`). This supersedes the earlier,
  never-activated `infrastructure/public_auth.py` module from an earlier
  batch, which is not part of the live request path.
- **`services/incoming_gatekeeper.py`**: `IncomingGatekeeper` bounds
  concurrent in-flight operations (semaphore) and the rolling per-minute
  rate (sliding window), config-driven from the existing `rate_limits.json`
  top-level block (30/min, 2 concurrent, queue 100), independent of the
  Gmail sender's own `Gatekeeper` (no shared mutable state). Cancellation,
  an exception, or a timeout inside an admitted slot all still release it
  (`tests/unit/test_incoming_gatekeeper.py`).
- **`sdk/public_mode.py`**: `resolve_public_tokens()` fails closed --
  `--public` with no (or a blank) `PUBLIC_BIND_TOKEN` refuses to start,
  never falls back to unauthenticated mode. `_ALLOWED_LOCAL_HOSTS`
  (`server_lifecycle.py`) is completely untouched by any of this --
  `--public` only changes whether middleware is attached, never what host
  is bound.
- **`infrastructure/mcp_client.py`**: adds `Authorization: Bearer <token>`
  via `fastmcp.client.auth.bearer.BearerAuth` (backed by `pydantic.SecretStr`,
  so it can't leak via a plain `repr()`) only when a token is given; a
  local/no-token call is byte-for-byte the same request it always was
  (`tests/unit/test_mcp_client_token.py`).

## Gate A1 correction — logical-operation rate limiting, not raw HTTP

The original Gate A1 rate limiter was ASGI-level, so it counted every raw
HTTP request FastMCP's streamable-HTTP transport happens to use underneath
one logical call (session initialize, `notifications/initialized`,
capability discovery, the real `tools/call`, session teardown -- roughly
6 raw requests per call). Appendix F Table 19's "30 requests per minute"
binding minimum is a logical-operation budget (the table's own worked
context, per this project's `rate_limits.json`, is an outbound API-call
Gatekeeper), so counting raw transport frames against it made the
committed 30/min config unable to sustain even light real gameplay --
discovered only by actually running a real authenticated two-process
series, not by any unit or single-server integration test.

- **`infrastructure/mcp_rate_limit_middleware.py`**: `McpRateLimitMiddleware`,
  a FastMCP protocol-level middleware (`Middleware.on_call_tool`,
  registered via `FastMCP.add_middleware` -- NOT the ASGI
  `http_app(middleware=...)` list) charges exactly one `IncomingGatekeeper`
  slot per real `tools/call` dispatch, before the tool body runs
  (`tests/unit/test_mcp_rate_limit_middleware.py`,
  `tests/integration/test_public_mode_http.py`). `health` is excluded
  (liveness/readiness probe, not a logical game operation). Auth stays
  ASGI-level, unchanged -- it must guard session establishment itself.
- **`infrastructure/outbound_pacer.py`**: `OutboundPacer` proactively
  WAITS (never rejects) for a rate/concurrency slot before an outbound call
  to a `--public` opponent, so a compliant client paces itself under the
  same binding minimums rather than bursting and relying on repeated
  overload responses (`tests/unit/test_outbound_pacer.py`). Only
  constructed when an opponent token is known (i.e. the opponent runs
  `--public`); ordinary local self-play never builds one
  (`tests/unit/test_pacer_gating.py`).
- **`infrastructure/mcp_client.py`**: a real overload response
  (`McpOverloadError`, a distinct JSON-RPC error code) is retried, honoring
  the server's own `retry_after_seconds` hint, up to `DEFAULT_MAX_RETRIES`
  (3 -- Table 19's binding minimum retry count) times, then becomes an
  ordinary `PeerUnavailableError` -- never retried indefinitely
  (`tests/unit/test_mcp_client_retry_backoff.py`).
- Real, real-HTTP proof (not just unit-level): `tests/integration/test_public_mode_http.py`
  (missing/wrong/correct token, one logical call charges the budget exactly
  once despite ~6 raw HTTP requests underneath, excess logical calls
  rejected before the tool runs, `health` never charged, auth rejection
  never charged, max-2-concurrent, still-127.0.0.1-only bind) and
  `tests/integration/test_public_mode_lifecycle.py` (repeated start/stop
  releases the same port, still no orphans). All of these run against
  `127.0.0.1` only, in-process -- no tunnel, no public exposure.
