import os
import sys
import json

# Detect if running as a PyInstaller executable
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    _APP_ROOT = os.path.dirname(sys.executable)
else:
    # Running as a script
    _APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Settings file location (in user's home directory for persistence)
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".cardwatcher_settings.json")


def load_settings():
    """Load settings from file."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_settings(settings):
    """Save settings to file."""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def get_data_dir():
    """Get the data directory from settings or return default."""
    settings = load_settings()
    if "data_dir" in settings and os.path.isdir(settings["data_dir"]):
        return settings["data_dir"]
    return None


def set_data_dir(path):
    """Set the data directory in settings."""
    settings = load_settings()
    settings["data_dir"] = path
    save_settings(settings)


def get_default_data_dir():
    """Get the default data directory path."""
    return os.path.normpath(os.path.join(_APP_ROOT, "..", "cardwatcher-data"))


def prompt_for_data_dir():
    """Show a dialog to select the data directory. Returns the selected path or None."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox

        root = tk.Tk()
        root.withdraw()  # Hide the main window

        # Show info message
        messagebox.showinfo(
            "CardWatcher Setup",
            "Welcome to CardWatcher!\n\n"
            "Please select the location for your data directory.\n"
            "This is where card data, images, and your collection will be stored."
        )

        # Get default path
        default_path = get_default_data_dir()
        initial_dir = os.path.dirname(default_path) if os.path.exists(os.path.dirname(default_path)) else os.path.expanduser("~")

        # Show folder selection dialog
        selected_dir = filedialog.askdirectory(
            title="Select CardWatcher Data Directory",
            initialdir=initial_dir
        )

        root.destroy()

        if selected_dir:
            return selected_dir
        return None
    except Exception as e:
        print(f"Error showing dialog: {e}")
        return None


def initialize_data_dir():
    """
    Initialize the data directory.
    If not configured, prompt user to select one.
    Returns the data directory path or None if cancelled.
    """
    data_dir = get_data_dir()

    if data_dir is None:
        # First run - prompt user
        data_dir = prompt_for_data_dir()

        if data_dir:
            set_data_dir(data_dir)
        else:
            # User cancelled - use default
            data_dir = get_default_data_dir()
            set_data_dir(data_dir)

    return data_dir


# Initialize DATA_DIR - will be set properly when initialize_data_dir() is called
DATA_DIR = get_data_dir() or get_default_data_dir()

PAGES_DIR = os.path.join(DATA_DIR, "pages")
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive")
IMAGES_DIR = os.path.join(DATA_DIR, "images")
CHANGES_DIR = os.path.join(DATA_DIR, "changes")

# Collection file location - stored in user's home directory (NOT in shared data dir)
# This ensures each user has their own private collection
COLLECTION_FILE = os.path.join(os.path.expanduser("~"), ".cardwatcher_collection.json")


def update_paths(data_dir):
    """Update all path constants with a new data directory.
    Note: COLLECTION_FILE is NOT updated - it stays in user's home directory."""
    global DATA_DIR, PAGES_DIR, ARCHIVE_DIR, IMAGES_DIR, CHANGES_DIR
    DATA_DIR = data_dir
    PAGES_DIR = os.path.join(DATA_DIR, "pages")
    ARCHIVE_DIR = os.path.join(DATA_DIR, "archive")
    IMAGES_DIR = os.path.join(DATA_DIR, "images")
    CHANGES_DIR = os.path.join(DATA_DIR, "changes")
