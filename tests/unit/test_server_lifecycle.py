"""Phase 1: managed FastMCP shutdown -- classification of intentional vs.
unexpected cancellation, and the scoped uvicorn-traceback log suppression.

These tests use a fake server coroutine (no real HTTP port, no real sleeps) so
the CancelledError classification is exercised deterministically. The log-filter
behaviour is checked by constructing LogRecords directly."""

from __future__ import annotations

import asyncio
import logging

import pytest

from thief_peer.infrastructure.server_lifecycle import (
    IntentionalShutdown,
    _ShutdownLogSuppressor,
    reset_shutdown_log_suppression,
    run_server_managed,
    stop_server,
)


class _FakeMCP:
    """Stand-in for FastMCP whose run_http_async blocks until cancelled."""

    def __init__(self) -> None:
        self.started = asyncio.Event()

    async def run_http_async(self, host: str, port: int, **kwargs: object) -> None:
        self.started.set()
        await asyncio.Event().wait()  # blocks forever until cancelled


def _cancelled_record() -> logging.LogRecord:
    """A record shaped like uvicorn's lifespan cancellation log (traceback text
    in the message, no exc_info)."""
    return logging.LogRecord(
        name="uvicorn.error",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Traceback (most recent call last):\n...\nasyncio.exceptions.CancelledError",
        args=(),
        exc_info=None,
    )


def _normal_error_record() -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.error",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Application startup failed: %s",
        args=("boom",),
        exc_info=None,
    )


def test_intentional_shutdown_is_silent_and_returns() -> None:
    """A cancellation after stop_server() (flag set) returns cleanly, no raise."""

    async def scenario() -> str:
        fake = _FakeMCP()
        shutdown = IntentionalShutdown()
        task = asyncio.create_task(run_server_managed(fake, "127.0.0.1", 0, shutdown))
        await fake.started.wait()
        await stop_server(task, shutdown)
        assert task.done()
        assert task.exception() is None  # returned, did not raise
        return "clean"

    assert asyncio.run(scenario()) == "clean"


def test_unexpected_cancellation_still_raises() -> None:
    """A cancellation with NO shutdown requested must re-raise CancelledError."""

    async def scenario() -> None:
        fake = _FakeMCP()
        shutdown = IntentionalShutdown()  # never .request()ed
        task = asyncio.create_task(run_server_managed(fake, "127.0.0.1", 0, shutdown))
        await fake.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())


def test_suppressor_drops_cancelled_traceback_only_when_requested() -> None:
    reset_shutdown_log_suppression()
    suppressor = _ShutdownLogSuppressor()
    shutdown = IntentionalShutdown()
    suppressor.register(shutdown)

    # Not requested yet: the cancellation traceback passes through.
    assert suppressor.filter(_cancelled_record()) is True

    shutdown.request()
    # Requested: the cancellation traceback is dropped...
    assert suppressor.filter(_cancelled_record()) is False
    # ...but an unrelated real error is never suppressed.
    assert suppressor.filter(_normal_error_record()) is True


def test_suppressor_drops_cancelled_via_exc_info() -> None:
    suppressor = _ShutdownLogSuppressor()
    shutdown = IntentionalShutdown()
    shutdown.request()
    suppressor.register(shutdown)
    record = logging.LogRecord(
        name="uvicorn.error",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="cancelled",
        args=(),
        exc_info=(asyncio.CancelledError, asyncio.CancelledError(), None),
    )
    assert suppressor.filter(record) is False


def test_intentional_shutdown_flag_semantics() -> None:
    shutdown = IntentionalShutdown()
    assert shutdown.requested is False
    shutdown.request()
    assert shutdown.requested is True
