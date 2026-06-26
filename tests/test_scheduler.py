"""WP5 tests: automated daily-refresh decision logic (faked clock, mock queue).
WP8 tests: schedule_status + relative-time formatting."""
import app.scheduler as scheduler_module
from app.scheduler import (
    AutoRefreshScheduler, should_auto_run, DAY_SECONDS,
    schedule_status, humanize_duration, time_ago, time_until,
)


# --- pure decision ----------------------------------------------------------

def test_should_auto_run_disabled():
    assert should_auto_run(now=1000, last_auto_run=0, enabled=False) is False


def test_should_auto_run_never_run():
    assert should_auto_run(now=1000, last_auto_run=0, enabled=True) is True


def test_should_auto_run_recent_is_skipped():
    now = 1_000_000
    last = now - (DAY_SECONDS // 2)  # half a day ago
    assert should_auto_run(now, last, enabled=True) is False


def test_should_auto_run_overdue_triggers():
    now = 1_000_000
    last = now - (DAY_SECONDS + 1)  # just over a day ago
    assert should_auto_run(now, last, enabled=True) is True


# --- maybe_run (catch-up vs skip) ------------------------------------------

def _patch_settings(monkeypatch, store):
    monkeypatch.setattr(scheduler_module, "get_setting",
                        lambda key, default=None: store.get(key, default))
    monkeypatch.setattr(scheduler_module, "set_setting",
                        lambda key, value: store.__setitem__(key, value))


def test_maybe_run_catches_up_when_overdue(monkeypatch):
    now = 2_000_000
    store = {"auto_import_enabled": True, "last_auto_run": now - 2 * DAY_SECONDS}
    _patch_settings(monkeypatch, store)
    calls = []
    sched = AutoRefreshScheduler(lambda: calls.append(1), clock=lambda: now)

    assert sched.maybe_run() is True
    assert calls == [1]
    # last_auto_run stamped so a second check the same day is a no-op.
    assert store["last_auto_run"] == now
    assert sched.maybe_run() is False
    assert calls == [1]


def test_maybe_run_skips_when_disabled(monkeypatch):
    now = 2_000_000
    store = {"auto_import_enabled": False, "last_auto_run": 0}
    _patch_settings(monkeypatch, store)
    calls = []
    sched = AutoRefreshScheduler(lambda: calls.append(1), clock=lambda: now)

    assert sched.maybe_run() is False
    assert calls == []
    assert store["last_auto_run"] == 0  # untouched


def test_maybe_run_skips_when_recent(monkeypatch):
    now = 2_000_000
    store = {"auto_import_enabled": True, "last_auto_run": now - 100}
    _patch_settings(monkeypatch, store)
    calls = []
    sched = AutoRefreshScheduler(lambda: calls.append(1), clock=lambda: now)

    assert sched.maybe_run() is False
    assert calls == []


# --- WP8: relative-time formatting -----------------------------------------

def test_humanize_duration_buckets():
    assert humanize_duration(30) == "less than a minute"
    assert humanize_duration(5 * 60) == "5m"
    assert humanize_duration(3 * 3600) == "3h"
    assert humanize_duration(2 * 86400) == "2d"
    # magnitude only — sign is ignored
    assert humanize_duration(-3 * 3600) == "3h"


def test_time_ago_and_until():
    now = 1_000_000
    assert time_ago(0, now) == "never"
    assert time_ago(now - 2 * 3600, now) == "2h ago"
    assert time_until(now + 3 * 3600, now) == "in 3h"
    assert time_until(now - 10, now) == "due now"


# --- WP8: schedule_status ---------------------------------------------------

def test_schedule_status_disabled(monkeypatch):
    now = 2_000_000
    _patch_settings(monkeypatch, {"auto_import_enabled": False,
                                  "last_auto_run": 0, "last_auto_finished": 0})
    s = schedule_status(now=now)
    assert s["enabled"] is False
    assert s["next_run_in"] == "off"
    assert s["last_finished_ago"] == "never"


def test_schedule_status_never_run_is_due(monkeypatch):
    now = 2_000_000
    _patch_settings(monkeypatch, {"auto_import_enabled": True,
                                  "last_auto_run": 0, "last_auto_finished": 0})
    s = schedule_status(now=now)
    assert s["enabled"] is True
    assert s["next_run_in"] == "due now"


def test_schedule_status_next_and_last(monkeypatch):
    now = 2_000_000
    _patch_settings(monkeypatch, {
        "auto_import_enabled": True,
        "last_auto_run": now - (DAY_SECONDS - 3 * 3600),   # next in ~3h
        "last_auto_finished": now - 2 * 3600,              # finished 2h ago
    })
    s = schedule_status(now=now)
    assert s["next_run_in"] == "in 3h"
    assert s["last_finished_ago"] == "2h ago"
    assert s["next_run"] == (now - (DAY_SECONDS - 3 * 3600)) + DAY_SECONDS
