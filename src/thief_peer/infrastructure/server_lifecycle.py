"""Clean, classified shutdown of the FastMCP HTTP server (Batch 2 Phase 1).

Cancelling the serving asyncio.Task is the intended way to stop the server, but
a bare ``Task.cancel()`` has two ugly side effects on a *clean* shutdown:

1. The ``CancelledError`` propagates out of the serving coroutine. We classify
   it in :func:`run_server_managed`: caught-and-silent when an intentional
   shutdown was requested, re-raised otherwise so an unexpected teardown still
   surfaces as an error.
2. uvicorn's ASGI lifespan logs the cancellation as an ERROR on the
   ``uvicorn.error`` logger, with the traceback baked into the *message string*
   (no ``exc_info``). This record fires from a late pending callback -- roughly
   400ms after the cancel, effectively at loop-teardown -- so a scoped
   add-then-remove filter cannot stay attached long enough to catch it. Instead a
   single persistent filter is installed once and consults the set of
   *currently-requested* intentional shutdowns, dropping the cancellation record
   only while such a shutdown is in progress. Nothing is suppressed globally: a
   cancellation with no shutdown requested, and every non-cancellation error,
   pass through untouched.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from fastmcp import FastMCP

logger = logging.getLogger("thief_peer.server_lifecycle")
_UVICORN_ERROR_LOGGER = "uvicorn.error"


class IntentionalShutdown:
    """A one-way flag recording that a shutdown was deliberately requested."""

    def __init__(self) -> None:
        self._requested = False

    def request(self) -> None:
        """Mark the next cancellation of the server task as intentional."""
        self._requested = True

    @property
    def requested(self) -> bool:
        """True once :meth:`request` has been called."""
        return self._requested


class _ShutdownLogSuppressor(logging.Filter):
    """Persistent ``uvicorn.error`` filter that drops the cancellation traceback
    only while a registered :class:`IntentionalShutdown` is in progress."""

    def __init__(self) -> None:
        super().__init__()
        self._active: set[IntentionalShutdown] = set()

    def register(self, shutdown: IntentionalShutdown) -> None:
        self._active.add(shutdown)

    def clear(self) -> None:
        """Forget all registered shutdowns (used to isolate tests)."""
        self._active.clear()

    def filter(self, record: logging.LogRecord) -> bool:
        if not any(s.requested for s in self._active):
            return True
        exc_info = record.exc_info
        if exc_info and exc_info[0] is not None and issubclass(exc_info[0], asyncio.CancelledError):
            return False
        try:
            message = record.getMessage()
        except (TypeError, ValueError):
            return True
        return "CancelledError" not in message


_suppressor: _ShutdownLogSuppressor | None = None


def _get_suppressor() -> _ShutdownLogSuppressor:
    """Install the persistent filter on first use and return it (idempotent)."""
    global _suppressor
    if _suppressor is None:
        _suppressor = _ShutdownLogSuppressor()
        logging.getLogger(_UVICORN_ERROR_LOGGER).addFilter(_suppressor)
    return _suppressor


def reset_shutdown_log_suppression() -> None:
    """Test hook: clear the registered-shutdown set so a later test that
    exercises an *unexpected* cancellation is not affected by an earlier one."""
    if _suppressor is not None:
        _suppressor.clear()


async def run_server_managed(
    mcp: FastMCP, host: str, port: int, shutdown: IntentionalShutdown
) -> None:
    """Serve HTTP until cancelled.

    When cancelled after ``shutdown.request()`` has been called, this returns
    quietly (a clean, intentional stop). When cancelled with the flag unset, the
    ``CancelledError`` is re-raised so an unexpected teardown still surfaces.
    """
    try:
        await mcp.run_http_async(host=host, port=port, show_banner=False, log_level="warning")
    except asyncio.CancelledError:
        if shutdown.requested:
            logger.info("server stopped: intentional shutdown (port %d)", port)
            return
        logger.error("server cancelled unexpectedly with no shutdown requested (port %d)", port)
        raise


async def stop_server(task: asyncio.Task, shutdown: IntentionalShutdown) -> None:
    """Request an intentional shutdown, then cancel and await the server task.

    Registers ``shutdown`` with the persistent log suppressor and sets the flag
    *before* cancelling, so both the propagating ``CancelledError`` and
    uvicorn's late lifespan log record are classified as clean.
    """
    _get_suppressor().register(shutdown)
    shutdown.request()
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
