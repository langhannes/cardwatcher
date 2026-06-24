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
