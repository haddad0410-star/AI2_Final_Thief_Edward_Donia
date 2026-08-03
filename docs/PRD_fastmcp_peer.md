# PRD fastmcp peer

## Purpose

Define this peer's FastMCP server+client responsibilities.

## Requirements

- Real HTTP transport (`transport="http"`), never an in-process mock in production code.
- Tool surface: `negotiate`, `receive_turn`, `submit_audit`, `receive_control` (see `_post4b_supplementary_evidence/audit/protocol_contract.md`).
- This peer is simultaneously server and client (book Ch.2, Fig.2 symmetric architecture, visually confirmed).
- No central referee; no shared state with the opponent process.

## Acceptance criteria (measurable)

- [x] Two local processes (this peer + the real opponent, `thief_peer`) complete a real
      HTTP round-trip — negotiation-smoke raw evidence was produced during development
      in the full multi-repo workspace and is not included in this single-repo package;
      the same real-HTTP round-trip is proven in-repo by
      `tests/integration/test_mcp_negotiation.py` (real stdout/stderr/exit codes, both
      sides report `outcome: "negotiated"`).
- [x] Duplicate-message handling behaves per the idempotency policy in the protocol
      contract — same correlation_id + same payload = idempotent accept, same
      correlation_id + different payload = `CONFLICTING_DUPLICATE`, both proven over
      real HTTP in `tests/integration/test_mcp_negotiation.py`.
- [x] Health-check endpoint responds before negotiation — `mcp_client.wait_for_health`,
      bounded retries, tested including the unavailable-peer case (clean timeout, no
      hang).
- [x] Full turn-by-turn game loop — `receive_turn`/`submit_audit`/`receive_control` are
      implemented and wired to the state machine (not schema-only), including the real
      bilateral result-agreement exchange over `submit_audit` — proven over real HTTP
      by `tests/integration/`, `tests/security/`, and repeated real two-process series
      (`_post4b_supplementary_evidence/batch4b/bilateral_series/`).

`health`/`negotiate`/`propose_config` were the only tools implemented in the original
Batch 1 vertical slice; `receive_turn`/`submit_audit`/`receive_control` have since been
fully implemented (see `docs/PROTOCOL.md`).

## Out of scope (for now)

Public tunnel exposure (Manual Gate A). Real opponent negotiation with another team
(Manual Gate B) — this batch's "real opponent" is our own `thief_peer` repo, run as a
genuinely separate process, not a stub.

Status: the full turn-by-turn game loop, commit-reveal, and mutual audit are
implemented, tested, and proven over real two-process HTTP — readiness `LOCAL_READY`.
`NETWORK_READY`/`LEAGUE_READY`/`SUBMISSION_READY` are not claimed (Manual Gates A/B
remain open). See `_post4b_supplementary_evidence/audit/PROGRESS.md`.
