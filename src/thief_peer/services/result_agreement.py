"""Real bilateral end-of-series result agreement (post-Batch-4B fix).
Independent implementation -- no import of the Police repository.

Each peer independently computes its own totals/digest, sends them via the
existing ``submit_audit`` tool as a ``result_agreement`` message, and
independently compares the opponent's submission against its own. No
cross-repo import, no shared memory -- only the existing FastMCP wire tools.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
from collections.abc import Iterable
from dataclasses import replace

from thief_peer.domain.roles import Role
from thief_peer.infrastructure.inbox import BoundedInbox
from thief_peer.infrastructure.mcp_client import PeerUnavailableError, call_submit_audit
from thief_peer.services.series_runtime import SeriesResult, SeriesSubGameRecord
from thief_peer.services.series_scoring import FinalAgreement, resolve_final_agreement


def compute_result_digest(records: Iterable[SeriesSubGameRecord]) -> str:
    """A single SHA-256 over every sub-game's (number, result, both scores,
    steps), in sub-game order -- catches a per-game score mismatch that
    happens to sum to the same series total."""
    canonical = [
        {
            "sub_game_number": r.sub_game_number,
            "result": r.result.value,
            "police_score": r.police_score,
            "thief_score": r.thief_score,
            "steps": r.steps_taken,
        }
        for r in sorted(records, key=lambda r: r.sub_game_number)
    ]
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def build_result_agreement_message(
    *,
    game_uid: str,
    sender: Role,
    config_sha256: str,
    police_total: int,
    thief_total: int,
    num_sub_games: int,
    result_digest: str,
) -> dict:
    return {
        "message_type": "result_agreement",
        "envelope": {
            "game_uid": game_uid,
            "sender": sender.value,
            "sub_game_number": 0,
            "step": 0,
            "sequence_id": 0,
        },
        "config_sha256": config_sha256,
        "police_total": police_total,
        "thief_total": thief_total,
        "num_sub_games": num_sub_games,
        "result_digest": result_digest,
    }


def _pop_opponent_agreement(inbox: BoundedInbox, opponent: Role) -> dict | None:
    return inbox.pop_matching(
        lambda m: (
            m.get("message_type") == "result_agreement"
            and m.get("envelope", {}).get("sender") == opponent.value
        )
    )


async def _await_opponent_agreement(
    inbox: BoundedInbox, opponent: Role, *, attempts: int, poll_interval: float
) -> dict | None:
    for _ in range(attempts):
        message = _pop_opponent_agreement(inbox, opponent)
        if message is not None:
            return message
        await asyncio.sleep(poll_interval)
    return None


async def exchange_and_resolve_agreement(
    *,
    opponent_url: str,
    inbox: BoundedInbox,
    game_uid: str,
    config_sha256: str,
    sender: Role,
    our_totals: tuple[int, int],
    num_sub_games: int,
    result_digest: str,
    attempts: int = 100,
    poll_interval: float = 0.1,
    opponent_token: str | None = None,
) -> FinalAgreement:
    # Send our own result, wait (bounded) for the opponent's, and resolve.
    # Never invents a their_* value: an unreachable opponent or a timed-out
    # wait both fall through to resolve_final_agreement's own
    # unverified_self_play path (their_police/their_thief stay None).
    our_police, our_thief = our_totals
    message = build_result_agreement_message(
        game_uid=game_uid,
        sender=sender,
        config_sha256=config_sha256,
        police_total=our_police,
        thief_total=our_thief,
        num_sub_games=num_sub_games,
        result_digest=result_digest,
    )
    with contextlib.suppress(PeerUnavailableError):
        await call_submit_audit(opponent_url, message, token=opponent_token)

    theirs = await _await_opponent_agreement(
        inbox, sender.opponent(), attempts=attempts, poll_interval=poll_interval
    )
    if theirs is None:
        return resolve_final_agreement(our_police, our_thief, None, None)
    if theirs.get("num_sub_games") != num_sub_games or theirs.get("result_digest") != result_digest:
        return FinalAgreement(False, "disputed_zeroed", 0, 0)
    return resolve_final_agreement(
        our_police, our_thief, theirs.get("police_total"), theirs.get("thief_total")
    )


async def finalize_series_agreement(
    series: SeriesResult,
    *,
    opponent_url: str,
    inbox: BoundedInbox,
    game_uid: str,
    config_sha256: str,
    role: Role,
    opponent_token: str | None = None,
) -> SeriesResult:
    """Replace the series' totals/agreement fields with the REAL bilaterally
    -exchanged result, only when the series itself completed normally (a
    technical loss keeps its own honest terminated_reason unchanged)."""
    if series.terminated_reason != "completed":
        return series
    digest = compute_result_digest(series.sub_games)
    agreement = await exchange_and_resolve_agreement(
        opponent_url=opponent_url,
        inbox=inbox,
        game_uid=game_uid,
        config_sha256=config_sha256,
        sender=role,
        our_totals=(series.police_total, series.thief_total),
        num_sub_games=len(series.sub_games),
        result_digest=digest,
        opponent_token=opponent_token,
    )
    return replace(
        series,
        police_total=agreement.police_total,
        thief_total=agreement.thief_total,
        agreed=agreement.agreed,
        agreement_status=agreement.status,
    )
