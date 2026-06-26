"""
Automated daily refresh (WP5).

A daemon thread that, when `auto_import_enabled` is set, queues a full refresh
on launch if the last run was more than a day ago (catch-up) and then re-checks
on an interval so a long-running instance refreshes itself once a day. The
`last_auto_run` timestamp prevents re-queuing within the same day.

The actual downloading/importing is owned by the download queue worker (WP4);
this module only decides *when* to enqueue a full refresh.
"""

import threading
import time

from app.config import get_setting, set_setting

DAY_SECONDS = 24 * 60 * 60
CHECK_INTERVAL = 60 * 60  # re-evaluate the schedule hourly while running


def humanize_duration(seconds):
    """Compact magnitude of a duration, e.g. '5m', '3h', '2d'."""
    seconds = int(abs(seconds))
    if seconds < 60:
        return "less than a minute"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def time_ago(ts, now):
    """'2h ago' for a past timestamp, 'never' for a falsy one."""
    if not ts:
        return "never"
    return f"{humanize_duration(now - ts)} ago"


def time_until(ts, now):
    """'in 3h' for a future timestamp, 'due now' once it has passed."""
    delta = ts - now
    if delta <= 0:
        return "due now"
    return f"in {humanize_duration(delta)}"


def schedule_status(now=None):
    """Snapshot of the auto-refresh schedule for the UI.

    Returns enabled flag, last finished time (real completion, WP8), and the
    next scheduled run — each with a friendly relative-time string.
    """
    now = now if now is not None else time.time()
    enabled = bool(get_setting('auto_import_enabled', False))
    last_run = get_setting('last_auto_run', 0) or 0
    last_finished = get_setting('last_auto_finished', 0) or 0

    if not enabled:
        next_run, next_run_in = 0, "off"
    elif not last_run:
        next_run, next_run_in = now, "due now"
    else:
        next_run = last_run + DAY_SECONDS
        next_run_in = time_until(next_run, now)

    return {
        "enabled": enabled,
        "last_finished": last_finished,
        "last_finished_ago": time_ago(last_finished, now),
        "last_run": last_run,
        "next_run": next_run,
        "next_run_in": next_run_in,
    }


def should_auto_run(now, last_auto_run, enabled, interval=DAY_SECONDS):
    """Pure decision: is an automated full refresh due?

    True when automation is enabled and either it has never run or at least
    `interval` seconds have elapsed since the last run.
    """
    if not enabled:
        return False
    if not last_auto_run:
        return True
    return (now - last_auto_run) >= interval


class AutoRefreshScheduler:
    """Owns the daily-refresh timer. `enqueue_refresh` is injected for testing."""

    def __init__(self, enqueue_refresh, check_interval=CHECK_INTERVAL,
                 interval=DAY_SECONDS, clock=time.time):
        self._enqueue_refresh = enqueue_refresh
        self._check_interval = check_interval
        self._interval = interval
        self._clock = clock
        self._thread = None
        self._stop = threading.Event()

    def maybe_run(self):
        """Evaluate the schedule once. Enqueue + stamp the run if due.

        Returns True if a refresh was triggered, False otherwise.
        """
        enabled = get_setting('auto_import_enabled', False)
        last = get_setting('last_auto_run', 0) or 0
        if should_auto_run(self._clock(), last, enabled, self._interval):
            self._enqueue_refresh()
            # Stamp immediately so we don't re-queue on the next check this day.
            set_setting('last_auto_run', self._clock())
            return True
        return False

    def _loop(self):
        # Catch-up on launch, then re-check on the interval.
        while not self._stop.is_set():
            try:
                self.maybe_run()
            except Exception as e:
                print(f"[scheduler] error: {e}")
            self._stop.wait(self._check_interval)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
