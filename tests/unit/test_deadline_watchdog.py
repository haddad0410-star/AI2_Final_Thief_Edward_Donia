"""Phase 3: DeadlineTracker and Watchdog -- all with an injected fake clock, so
no test ever sleeps for a real 30 or 60 seconds."""

from __future__ import annotations

from thief_peer.domain.captures import SubGameResult
from thief_peer.domain.deadline import DeadlineTracker
from thief_peer.domain.watchdog import Watchdog, WatchdogStatus


class FakeClock:
    """A manually-advanced monotonic clock for deterministic time tests."""

    def __init__(self, start: float = 1000.0) -> None:
        self._t = start

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


# --- DeadlineTracker -------------------------------------------------------


def test_deadline_normal_operation_within_budget() -> None:
    clock = FakeClock()
    d = DeadlineTracker(30.0, now_fn=clock).start()
    clock.advance(10.0)
    assert d.elapsed() == 10.0
    assert d.remaining() == 20.0
    assert d.expired() is False


def test_deadline_response_after_deadline_clamps_to_zero() -> None:
    clock = FakeClock()
    d = DeadlineTracker(30.0, now_fn=clock).start()
    clock.advance(45.0)
    assert d.remaining() == 0.0  # never negative
    assert d.expired() is True


def test_deadline_child_capped_by_parent_remaining() -> None:
    clock = FakeClock()
    parent = DeadlineTracker(30.0, now_fn=clock).start()
    clock.advance(25.0)  # 5s left
    child = parent.child(20.0)  # asked 20, capped to 5
    assert child.remaining() == 5.0
    clock.advance(5.0)
    assert child.expired() is True


def test_deadline_auto_starts_on_query() -> None:
    clock = FakeClock()
    d = DeadlineTracker(10.0, now_fn=clock)
    assert d.remaining() == 10.0  # auto-start


# --- Watchdog --------------------------------------------------------------


def test_watchdog_healthy_when_progress_is_fresh() -> None:
    clock = FakeClock()
    w = Watchdog(60.0, now_fn=clock)
    clock.advance(30.0)
    assert w.check().status is WatchdogStatus.HEALTHY


def test_watchdog_activation_on_stall_requests_graceful_first() -> None:
    clock = FakeClock()
    w = Watchdog(60.0, now_fn=clock)
    clock.advance(61.0)
    out = w.check()
    assert out.status is WatchdogStatus.GRACEFUL_SHUTDOWN
    assert "graceful" in out.reason


def test_watchdog_progress_resets_stall_timer() -> None:
    clock = FakeClock()
    w = Watchdog(60.0, now_fn=clock)
    clock.advance(59.0)
    w.note_progress()
    clock.advance(59.0)
    assert w.check().status is WatchdogStatus.HEALTHY


def test_watchdog_retry_exhaustion_yields_technical_loss() -> None:
    clock = FakeClock()
    w = Watchdog(10.0, max_retries=2, now_fn=clock)
    clock.advance(11.0)
    assert w.check().status is WatchdogStatus.GRACEFUL_SHUTDOWN  # escalation 1
    assert w.check().status is WatchdogStatus.ESCALATED  # escalation 2
    out = w.check()  # escalation 3 > max_retries
    assert out.status is WatchdogStatus.TECHNICAL_LOSS
    assert out.is_technical_loss is True
    assert out.sub_game_result() is SubGameResult.TECHNICAL_LOSS


def test_watchdog_dead_subprocess_is_immediate_technical_loss() -> None:
    """Models an 'opponent unavailable' / dead local helper: a fatal outcome."""
    clock = FakeClock()
    w = Watchdog(60.0, now_fn=clock)
    w.note_subprocess_dead("opponent process unreachable")
    out = w.check()
    assert out.status is WatchdogStatus.TECHNICAL_LOSS
    assert "unreachable" in out.reason


def test_watchdog_malformed_response_loop_is_bounded() -> None:
    """A repeating malformed-response loop keeps noting no progress; the
    watchdog must terminate it, never spin forever."""
    clock = FakeClock()
    w = Watchdog(5.0, max_retries=3, now_fn=clock)
    outcomes = []
    for _ in range(10):  # simulate a long malformed-reply loop
        clock.advance(6.0)
        out = w.check()
        outcomes.append(out.status)
        if out.is_technical_loss:
            break
    assert outcomes[-1] is WatchdogStatus.TECHNICAL_LOSS
    assert len(outcomes) <= 4  # bounded by max_retries + 1, not 10


def test_watchdog_clean_shutdown_no_false_alarm() -> None:
    clock = FakeClock()
    w = Watchdog(60.0, now_fn=clock)
    # steady progress, then a clean stop -- never escalates.
    for _ in range(5):
        clock.advance(30.0)
        w.note_progress()
    assert w.escalations == 0
    assert w.check().status is WatchdogStatus.HEALTHY
