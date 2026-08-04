# PRD gmail reporter

## Purpose

Define the automated Gmail reporting tool.

## Requirements

- Scope `gmail.send` only (Appendix A, visually confirmed p.107-108).
- Recipient `rmisegal+uoh26finalgame@gmail.com` (Appendix F Table 20, visually confirmed).
- Credentials outside the repo via `GOOGLE_OAUTH_CREDENTIAL_DIR`.
- Modes: dry-run (default), draft, send (`--send`, requires your explicit approval each time — Manual Gate C).
- Report body is structured JSON, attached, not free text (Ch.9.3.3).

## Acceptance criteria (measurable)

- [x] Dry-run mode produces a valid report JSON without any network call — `tests/unit/test_gmail_sender.py::test_dry_run_never_touches_network`.
- [x] A test with mocked Gmail client proves draft/send code paths work without touching a real account — `tests/unit/test_gmail_sender.py`, `tests/unit/test_gmail_gatekeeper.py`.
- [x] Missing OAuth files produce a clear error, not a silent failure — `tests/security/test_gmail_credentials.py`.

## Out of scope (for now)

Real send/draft execution (never run unattended — Manual Gate C).

Status: implemented and tested (Batch 4A dry-run reporter, behind a real token-bucket
Gatekeeper). `--send` exists in code but has never been invoked; real Gmail delivery
remains gated behind Manual Gate C. See `_post4b_supplementary_evidence/audit/PROGRESS.md`.
