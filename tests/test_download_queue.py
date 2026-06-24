"""WP4 tests: download priority queue, enqueue ordering, status shape."""
import itertools
import queue
import time

import pytest

import app.download_manager as dm_module
from app.download_manager import DownloadManager, DownloadStatus


@pytest.fixture
def dm(monkeypatch):
    """The singleton manager with a fresh queue and no real worker thread."""
    manager = DownloadManager()
    manager._queue = queue.PriorityQueue()
    manager._seq = itertools.count()
    manager._go_idle()
    # Don't spawn the background worker in pure-logic tests.
    monkeypatch.setattr(manager, "_ensure_worker", lambda: None)
    return manager


def _drain(manager):
    items = []
    try:
        while True:
            items.append(manager._queue.get_nowait())
    except queue.Empty:
        pass
    return items


# --- enqueue contracts ------------------------------------------------------

def test_download_single_page_returns_queued_position(dm):
    result = dm.download_single_page("Some_Card.json")
    assert result["success"] is True
    assert result["queued"] is True
    assert result["position"] == 0
    # Strips .json and enqueues a high-priority single job.
    items = _drain(dm)
    assert len(items) == 1
    priority, _seq, kind, name = items[0]
    assert priority == DownloadManager.PRIORITY_SINGLE
    assert kind == "single"
    assert name == "Some_Card"


def test_download_from_url_enqueues_single(dm):
    result = dm.download_from_url(
        "https://www.cardmarket.com/en/Pokemon/Products/Singles/Set/Card")
    assert result["queued"] is True
    items = _drain(dm)
    assert items[0][2] == "single"
    assert items[0][3] == "Pokemon_Products_Singles_Set_Card"


def test_download_from_url_rejects_non_cardmarket(dm):
    result = dm.download_from_url("https://example.com/foo")
    assert result["success"] is False


# --- ordering: single jumps ahead of the full-refresh backlog ---------------

def test_single_jumps_ahead_of_bulk(dm, monkeypatch, tmp_path):
    # Populate the bulk backlog as a full refresh would.
    pages = tmp_path / "pages"
    pages.mkdir()
    for n in ("A", "B", "C"):
        (pages / (n + ".json")).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(dm_module, "PAGES_DIR", str(pages))
    monkeypatch.setattr(dm_module, "get_already_downloaded", lambda: set())

    queued = dm._expand_full_refresh()
    assert queued == 3

    # A user clicks Download on one card.
    dm.download_single_page("Urgent_Card")

    # The very next job served is the single, ahead of all bulk jobs.
    priority, _seq, kind, name = dm._queue.get_nowait()
    assert kind == "single"
    assert name == "Urgent_Card"
    # everything left is bulk
    assert all(item[2] == "bulk" for item in _drain(dm))


def test_expand_full_refresh_skips_already_downloaded(dm, monkeypatch, tmp_path):
    pages = tmp_path / "pages"
    pages.mkdir()
    for n in ("A", "B", "C"):
        (pages / (n + ".json")).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(dm_module, "PAGES_DIR", str(pages))
    monkeypatch.setattr(dm_module, "get_already_downloaded", lambda: {"B"})

    queued = dm._expand_full_refresh()
    assert queued == 2
    assert dm._skipped_pages == 1


def test_start_guards_against_duplicate_refresh(dm):
    first = dm.start()
    assert first["success"] is True
    # A full refresh is already pending -> second start is rejected.
    second = dm.start()
    assert second["success"] is False


# --- rate-limit gate --------------------------------------------------------

def test_wait_before_bulk_no_wait_when_due(dm):
    dm._next_bulk_time = time.time() - 1
    assert dm._wait_before_bulk() is True


def test_wait_before_bulk_yields_to_single(dm):
    dm._next_bulk_time = time.time() + 1000  # far in the future
    dm._queue.put((DownloadManager.PRIORITY_SINGLE, next(dm._seq), "single", "X"))
    # A single is waiting, so the bulk job must stand aside immediately.
    assert dm._wait_before_bulk() is False


# --- status shape -----------------------------------------------------------

def test_get_status_shape(dm):
    dm.download_single_page("Card_One")
    status = dm.get_status()
    for key in ("status", "total", "completed", "skipped", "failed",
                "current_page", "current_job_kind", "queue_length",
                "wait_remaining", "progress_percent", "import_failed",
                "finished"):
        assert key in status
    assert status["queue_length"] == 1
    assert status["total"] == 1
    assert status["status"] == DownloadStatus.IDLE.value


# --- end-to-end worker (selenium mocked) ------------------------------------

def test_worker_processes_single_and_imports(monkeypatch):
    manager = DownloadManager()
    manager._queue = queue.PriorityQueue()
    manager._seq = itertools.count()
    manager._go_idle()

    monkeypatch.setattr(dm_module, "create_browser", lambda: object())
    monkeypatch.setattr(dm_module, "is_session_valid", lambda d: True)
    monkeypatch.setattr(dm_module, "download_page_with_selenium",
                        lambda d, name, c: "success")
    imported = {"count": 0}

    def fake_import():
        imported["count"] += 1
        return {"imported": 1, "skipped": 0, "failed": [], "rows_skipped": 0}

    monkeypatch.setattr(dm_module.watcherbase, "import_all_pages", fake_import)

    manager.download_single_page("Worker_Card")

    # Wait (briefly) for the worker to drain the job.
    deadline = time.time() + 5
    while time.time() < deadline and "Worker_Card" not in manager.get_status()["finished"]:
        time.sleep(0.05)

    status = manager.get_status()
    assert "Worker_Card" in status["finished"]
    assert status["completed"] == 1
    assert imported["count"] >= 1

    manager.stop()
