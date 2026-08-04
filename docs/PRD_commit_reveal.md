# PRD commit reveal

## Purpose

Define the cryptographic sealing and mutual audit protocol.

## Requirements

- `H_commit = SHA256(canonical_json({state, move, intent, nonce}))`, fresh CSPRNG nonce per step, hidden until final reveal (Ch.5.3, visually confirmed Fig.6 sequence: Commit -> Acknowledge -> Reveal -> Audit).
- Constant-time comparison on verify (`secrets.compare_digest`).
- Step-0 hardware declaration, sealed before the first move.
- Any recomputation mismatch = `tamper_forfeit`, no partial credit.

## Acceptance criteria (measurable)

- [x] Security tests deliberately alter move/hint/verdict/nonce/step/config/capture-answer/record-order — every alteration is detected (`tests/security/test_tamper.py`, 13 single-field mutation cases plus record-order/gap detection).
- [x] No nonce is ever reused across steps — `tests/unit/test_sealing.py::test_nonce_reuse_is_detected`.
- [x] Constant-time comparison verified (no early-exit branching on mismatch position) — `secrets.compare_digest` used throughout `domain/sealing/audit.py`, verified via monkeypatch spy in `tests/unit/test_sealing.py`.

## Out of scope (for now)

GUI/replay display of audit results (see PRD_gui_replay.md).

Status: implemented and tested. Unified under the `commitment/1` schema (Batch 4B) for
bilateral verification. See `_post4b_supplementary_evidence/audit/PROGRESS.md`.
