"""
Download manager for running Selenium downloads in a background thread.
Provides start/stop/status functionality for the web interface.
"""

import threading
import time
import os
from enum import Enum

# Import selenium downloader functions
from app.selenium_downloader import (
    create_browser,
    is_session_valid,
    get_already_downloaded,
    download_page_with_selenium
)
from app.watcherbase import watcherbase
from app.config import PAGES_DIR


class DownloadStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    WAITING = "waiting"
    IMPORTING = "importing"


class DownloadManager:
    """Singleton manager for background downloads with progress tracking."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._status = DownloadStatus.IDLE
        self._thread = None
        self._stop_requested = False

        # Progress tracking
        self._total_pages = 0
        self._completed_pages = 0
        self._skipped_pages = 0
        self._failed_pages = 0
        self._current_page = ""
        self._wait_remaining = 0  # seconds remaining in wait period
        self._last_error = ""

    def get_status(self):
        """Get current download status and progress."""
        return {
            "status": self._status.value,
            "total": self._total_pages,
            "completed": self._completed_pages,
            "skipped": self._skipped_pages,
            "failed": self._failed_pages,
            "current_page": self._current_page,
            "wait_remaining": self._wait_remaining,
            "last_error": self._last_error,
            "progress_percent": self._calculate_progress()
        }

    def _calculate_progress(self):
        """Calculate progress percentage."""
        if self._total_pages == 0:
            return 0
        return int((self._completed_pages + self._failed_pages) / self._total_pages * 100)

    def start(self):
        """Start the download process in a background thread."""
        with self._lock:
            if self._status != DownloadStatus.IDLE:
                return {"success": False, "message": "Download already in progress"}

            self._stop_requested = False
            self._status = DownloadStatus.RUNNING
            self._reset_progress()

            self._thread = threading.Thread(target=self._download_worker, daemon=True)
            self._thread.start()

            return {"success": True, "message": "Download started"}

    def stop(self):
        """Request the download to stop."""
        with self._lock:
            if self._status == DownloadStatus.IDLE:
                return {"success": False, "message": "No download in progress"}

            self._stop_requested = True
            self._status = DownloadStatus.STOPPING

            return {"success": True, "message": "Stop requested"}

    def _reset_progress(self):
        """Reset progress tracking."""
        self._total_pages = 0
        self._completed_pages = 0
        self._skipped_pages = 0
        self._failed_pages = 0
        self._current_page = ""
        self._wait_remaining = 0
        self._last_error = ""

    def download_single_page(self, page_name):
        """Download a single page synchronously. Returns result dict."""
        with self._lock:
            if self._status != DownloadStatus.IDLE:
                return {"success": False, "message": "Another download is in progress"}

            self._status = DownloadStatus.RUNNING
            self._reset_progress()
            self._total_pages = 1
            self._current_page = page_name

        driver = None
        result = {"success": False, "message": ""}

        try:
            # Initialize browser
            driver = create_browser()
            if driver is None:
                result["message"] = "Failed to initialize browser"
                return result

            # Download the page
            download_result = download_page_with_selenium(driver, page_name + ".json", 0)

            if download_result == "success":
                self._completed_pages = 1
                # Import the downloaded page
                self._status = DownloadStatus.IMPORTING
                self._current_page = "Importing..."
                try:
                    watcherbase.import_all_pages()
                except Exception as e:
                    print(f"[WARNING] Import failed: {e}")
                result["success"] = True
                result["message"] = "Download and import completed"
            elif download_result == "invalid_session":
                result["message"] = "Session invalid - please try again"
            else:
                self._failed_pages = 1
                result["message"] = "Download failed"

        except Exception as e:
            result["message"] = str(e)

        finally:
            if driver is not None:
                try:
                    driver.quit()
                except:
                    pass
            self._current_page = ""
            self._status = DownloadStatus.IDLE

        return result

    def _download_worker(self):
        """Background worker that performs the downloads."""
        driver = None

        try:
            # Get list of pages to download with their modification times
            page_files = []
            for f in os.listdir(PAGES_DIR):
                if f.endswith(".json"):
                    filepath = os.path.join(PAGES_DIR, f)
                    mtime = os.path.getmtime(filepath)
                    page_files.append((f, mtime))

            if not page_files:
                self._last_error = "No pages found in pages/ directory"
                return

            # Sort by modification time (oldest first)
            page_files.sort(key=lambda x: x[1])

            # Check which pages have already been downloaded
            already_downloaded = get_already_downloaded()
            pages_to_download = []

            for page, mtime in page_files:
                page_name_no_ext = page[:-5]
                if page_name_no_ext in already_downloaded:
                    self._skipped_pages += 1
                else:
                    pages_to_download.append(page)

            self._total_pages = len(pages_to_download)

            if self._total_pages == 0:
                self._last_error = "All pages already downloaded"
                return

            # Initialize browser
            self._current_page = "Initializing browser..."
            driver = create_browser()

            if driver is None:
                self._last_error = "Failed to initialize browser"
                return

            counter = len(already_downloaded)
            i = 0

            while i < len(pages_to_download):
                # Check for stop request
                if self._stop_requested:
                    break

                page_name = pages_to_download[i]
                self._current_page = page_name[:-5] if page_name.endswith('.json') else page_name

                # Check session validity
                if not is_session_valid(driver):
                    self._current_page = "Restarting browser..."
                    try:
                        driver.quit()
                    except:
                        pass
                    driver = create_browser()
                    if driver is None:
                        self._last_error = "Failed to restart browser"
                        break

                # Download the page
                result = download_page_with_selenium(driver, page_name, counter)

                if result == "success":
                    self._completed_pages += 1
                    counter += 1
                    i += 1

                    # Import immediately after successful download
                    self._status = DownloadStatus.IMPORTING
                    self._current_page = "Importing downloaded pages..."
                    try:
                        watcherbase.import_all_pages()
                    except Exception as e:
                        print(f"[WARNING] Import failed: {e}")
                    self._status = DownloadStatus.RUNNING

                elif result == "invalid_session":
                    # Retry after restarting browser
                    try:
                        driver.quit()
                    except:
                        pass
                    driver = create_browser()
                    if driver is None:
                        self._last_error = "Failed to restart browser"
                        break
                    continue
                else:  # "failed"
                    self._failed_pages += 1
                    counter += 1
                    i += 1

                # Wait between downloads (unless stopping or last page)
                if not self._stop_requested and i < len(pages_to_download):
                    self._status = DownloadStatus.WAITING
                    wait_seconds = int(5 * 60 + (5 * 60 * (i / len(pages_to_download))))  # 5-10 min
                    wait_seconds = min(wait_seconds, 10 * 60)  # Cap at 10 min

                    self._wait_remaining = wait_seconds
                    self._current_page = "Waiting before next download..."

                    while self._wait_remaining > 0 and not self._stop_requested:
                        time.sleep(1)
                        self._wait_remaining -= 1

                    self._status = DownloadStatus.RUNNING

        except Exception as e:
            self._last_error = str(e)

        finally:
            # Clean up browser
            if driver is not None:
                try:
                    driver.quit()
                except:
                    pass

            self._current_page = ""
            self._status = DownloadStatus.IDLE


# Global instance
download_manager = DownloadManager()
