"""WP5 tests: automated daily-refresh decision logic (faked clock, mock queue)."""
import app.scheduler as scheduler_module
from app.scheduler import AutoRefreshScheduler, should_auto_run, DAY_SECONDS


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
