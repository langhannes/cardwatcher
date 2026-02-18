"""
Data synchronization for CardWatcher.
Supports pulling from and pushing to GitHub repository.
"""
import os
import json
import time
import subprocess
import shutil
from app.config import PAGES_DIR, ARCHIVE_DIR, IMAGES_DIR, CHANGES_DIR

# Base data directory (parent of pages/)
DATA_DIR = os.path.dirname(PAGES_DIR)
SYNC_STATE_FILE = os.path.join(DATA_DIR, "sync_state.json")


class SyncManager:
    """Manages synchronization with remote Git repository."""

    def __init__(self):
        self.status = "idle"
        self.message = ""
        self.progress = 0
        self.details = {}

    def get_status(self):
        return {
            "status": self.status,
            "message": self.message,
            "progress": self.progress,
            "details": self.details
        }

    def _run_git(self, args, cwd=None):
        """Run a git command and return (success, output)."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=cwd or DATA_DIR,
                capture_output=True,
                text=True,
                timeout=120
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except FileNotFoundError:
            return False, "Git not found. Please install Git."
        except Exception as e:
            return False, str(e)

    def _is_git_repo(self):
        """Check if data directory is a git repository."""
        return os.path.exists(os.path.join(DATA_DIR, ".git"))

    def _get_current_commit(self):
        """Get current commit hash."""
        success, output = self._run_git(["rev-parse", "HEAD"])
        return output.strip() if success else None

    def _get_remote_url(self):
        """Get remote origin URL."""
        success, output = self._run_git(["remote", "get-url", "origin"])
        return output.strip() if success else None

    def _load_sync_state(self):
        """Load sync state from file."""
        if os.path.exists(SYNC_STATE_FILE):
            try:
                with open(SYNC_STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"last_sync": None, "remote_commit": None}

    def _save_sync_state(self, state):
        """Save sync state to file."""
        with open(SYNC_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def check_sync_available(self):
        """Check if sync is possible and return status info."""
        if not self._is_git_repo():
            return {
                "available": False,
                "git_installed": self._check_git_installed(),
                "is_repo": False,
                "remote_url": None,
                "message": "Data directory is not a Git repository"
            }

        remote_url = self._get_remote_url()
        state = self._load_sync_state()

        return {
            "available": True,
            "git_installed": True,
            "is_repo": True,
            "remote_url": remote_url,
            "last_sync": state.get("last_sync"),
            "message": "Ready to sync"
        }

    def _check_git_installed(self):
        """Check if git is installed."""
        try:
            subprocess.run(["git", "--version"], capture_output=True, timeout=5)
            return True
        except:
            return False

    def pull_only(self):
        """
        Pull latest data from remote without pushing local changes.
        This is safe and doesn't require write access to the repo.
        """
        self.status = "running"
        self.message = "Starting pull..."
        self.progress = 0
        self.details = {}

        try:
            # Check if git repo exists
            if not self._is_git_repo():
                self.status = "error"
                self.message = "Not a Git repository"
                return {"success": False, "message": self.message}

            # Stash any local changes
            self.message = "Stashing local changes..."
            self.progress = 10
            self._run_git(["stash"])

            # Fetch from remote
            self.message = "Fetching from remote..."
            self.progress = 30
            success, output = self._run_git(["fetch", "origin"])
            if not success:
                self.status = "error"
                self.message = f"Fetch failed: {output}"
                return {"success": False, "message": self.message}

            # Get current and remote commit
            current_commit = self._get_current_commit()
            success, remote_commit = self._run_git(["rev-parse", "origin/main"])
            if not success:
                # Try master branch
                success, remote_commit = self._run_git(["rev-parse", "origin/master"])

            remote_commit = remote_commit.strip() if success else None

            # Check if we're behind
            if current_commit == remote_commit:
                self.status = "idle"
                self.message = "Already up to date"
                self.progress = 100
                # Pop stash
                self._run_git(["stash", "pop"])
                return {"success": True, "message": "Already up to date", "updated": 0}

            # Pull changes (rebase to keep local commits on top)
            self.message = "Pulling changes..."
            self.progress = 50
            success, output = self._run_git(["pull", "--rebase", "origin", "main"])
            if not success:
                # Try master
                success, output = self._run_git(["pull", "--rebase", "origin", "master"])

            if not success:
                # Abort rebase if it failed
                self._run_git(["rebase", "--abort"])
                self._run_git(["stash", "pop"])
                self.status = "error"
                self.message = f"Pull failed: {output}"
                return {"success": False, "message": self.message}

            # Pop stash to restore local changes
            self.message = "Restoring local changes..."
            self.progress = 80
            self._run_git(["stash", "pop"])

            # Update sync state
            state = self._load_sync_state()
            state["last_sync"] = time.time()
            state["remote_commit"] = self._get_current_commit()
            self._save_sync_state(state)

            self.status = "idle"
            self.message = "Pull completed successfully"
            self.progress = 100

            return {
                "success": True,
                "message": "Pull completed successfully",
                "previous_commit": current_commit[:8] if current_commit else None,
                "new_commit": state["remote_commit"][:8] if state["remote_commit"] else None
            }

        except Exception as e:
            self.status = "error"
            self.message = f"Error: {str(e)}"
            return {"success": False, "message": str(e)}

    def full_sync(self):
        """
        Full sync: pull changes, merge, and push local changes.
        Requires write access to the repository.
        """
        self.status = "running"
        self.message = "Starting full sync..."
        self.progress = 0
        self.details = {}

        try:
            # Check if git repo exists
            if not self._is_git_repo():
                self.status = "error"
                self.message = "Not a Git repository"
                return {"success": False, "message": self.message}

            # Check for uncommitted changes
            success, output = self._run_git(["status", "--porcelain"])
            has_changes = bool(output.strip())

            # If there are changes, commit them first
            if has_changes:
                self.message = "Committing local changes..."
                self.progress = 10

                # Add all changes
                self._run_git(["add", "-A"])

                # Commit
                commit_msg = f"CardWatcher sync - {time.strftime('%Y-%m-%d %H:%M')}"
                success, output = self._run_git(["commit", "-m", commit_msg])
                if not success and "nothing to commit" not in output:
                    self.status = "error"
                    self.message = f"Commit failed: {output}"
                    return {"success": False, "message": self.message}

            # Pull with rebase
            self.message = "Pulling remote changes..."
            self.progress = 30
            success, output = self._run_git(["pull", "--rebase", "origin", "main"])
            if not success:
                success, output = self._run_git(["pull", "--rebase", "origin", "master"])

            if not success:
                # Abort rebase if failed
                self._run_git(["rebase", "--abort"])
                self.status = "error"
                self.message = f"Pull failed: {output}"
                return {"success": False, "message": self.message}

            # Push local commits
            self.message = "Pushing local changes..."
            self.progress = 70
            success, output = self._run_git(["push", "origin", "main"])
            if not success:
                success, output = self._run_git(["push", "origin", "master"])

            if not success:
                self.status = "error"
                self.message = f"Push failed: {output}"
                return {"success": False, "message": self.message}

            # Update sync state
            state = self._load_sync_state()
            state["last_sync"] = time.time()
            state["remote_commit"] = self._get_current_commit()
            self._save_sync_state(state)

            self.status = "idle"
            self.message = "Full sync completed successfully"
            self.progress = 100

            return {
                "success": True,
                "message": "Full sync completed",
                "pushed": has_changes
            }

        except Exception as e:
            self.status = "error"
            self.message = f"Error: {str(e)}"
            return {"success": False, "message": str(e)}

    def get_last_sync_info(self):
        """Get information about last sync."""
        state = self._load_sync_state()
        last_sync = state.get("last_sync")

        if last_sync:
            # Calculate time since last sync
            elapsed = time.time() - last_sync
            if elapsed < 60:
                time_ago = "just now"
            elif elapsed < 3600:
                time_ago = f"{int(elapsed / 60)} minutes ago"
            elif elapsed < 86400:
                time_ago = f"{int(elapsed / 3600)} hours ago"
            else:
                time_ago = f"{int(elapsed / 86400)} days ago"
        else:
            time_ago = "never"

        return {
            "last_sync": last_sync,
            "time_ago": time_ago,
            "remote_commit": state.get("remote_commit")
        }


# Global sync manager instance
sync_manager = SyncManager()
