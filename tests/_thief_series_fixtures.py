"""Shared test-only fixtures for sub-game/series runtime tests (Phases 9-10):
the binding config, and two in-process FAKE opponent gateways. Mocks are
test-only -- production always speaks real FastMCP HTTP via
``services.gateway.HttpOpponentGateway``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from thief_peer.shared.config_loader import load_shared_config, sha256_hex

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "thief" / "game.json"
CONFIG = load_shared_config(CONFIG_PATH)
CFG_SHA = sha256_hex(CONFIG_PATH)
THIEF_START = list(CONFIG.board_and_agents.thief_start)


class FakeGateway:
    """A test-only opponent: acks everything, optionally injects public info."""

    def __init__(self, *, reject: bool = False, opponent_turn: dict | None = None) -> None:
        self._reject = reject
        self._opponent_turn = opponent_turn or {}
        self.turns_seen: list[str] = []

    async def deliver_turn(self, message: dict) -> dict:
        self.turns_seen.append(message["message_type"])
        if self._reject:
            return {"ok": False, "error_code": "MALFORMED", "reason": "test rejection"}
        ack: dict = {"ok": True}
        if message["message_type"] == "reveal":
            ack["opponent_turn"] = self._opponent_turn
        return ack

    async def deliver_audit(self, payload: dict) -> dict:
        return {"ok": True}


class BlockingGateway:
    """A test-only opponent whose ``deliver_turn`` never completes, so a
    caller can cancel the runtime while it is genuinely suspended mid-turn."""

    async def deliver_turn(self, message: dict) -> dict:
        await asyncio.Event().wait()

    async def deliver_audit(self, payload: dict) -> dict:
        return {"ok": True}
