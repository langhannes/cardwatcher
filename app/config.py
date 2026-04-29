import os
import sys
import json

# Detect if running as a PyInstaller executable
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    _APP_ROOT = os.path.dirname(sys.executable)
    IS_FROZEN = True
else:
    # Running as a script
    _APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    IS_FROZEN = False

# Settings file location (in user's home directory for persistence)
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".cardwatcher_settings.json")

# Default settings schema
DEFAULT_SETTINGS = {
    # Data directory (set via prompt on first run)
    "data_dir": None,
    "collection_file": None,  # Path to collection JSON (default: ~/.cardwatcher_collection.json)

    # Server settings
    "port": 5000,
    "auto_open_browser": True,
    "show_console": True,  # Show console/terminal window

    # Download settings
    "download_wait_min": 5,       # Minimum wait between downloads (minutes)
    "download_wait_max": 10,      # Maximum wait between downloads (minutes)
    "page_load_timeout": 30,      # Cloudflare/page load timeout (seconds)
    "show_more_limit": 20,        # Max "Show More" button clicks
    "browser_headless": False,    # Run browser in headless mode
    "browser_minimized": True,    # Start browser minimized

    # Display defaults
    "default_sort_by": "name",           # name, price, priceChange, percentChange, lowestPrice
    "default_sort_order": "asc",         # asc, desc
    "default_price_period": "last",      # last, 1w, 1m, 2m, 6m
    "default_price_type": "available",   # available, sold

    # Collection defaults
    "default_condition": "NM",           # MT, NM, EX, GD, LP, PL, PO
    "default_history_period": "2m",      # 2w, 2m, 6m, 1y
    "default_history_mode": "acquisition",  # acquisition, portfolio
}


def load_settings():
    """Load settings from file, merged with defaults."""
    settings = DEFAULT_SETTINGS.copy()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                # Merge saved settings over defaults
                settings.update(saved)
        except (json.JSONDecodeError, IOError):
            pass
    return settings


def save_settings(settings):
    """Save settings to file."""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def get_setting(key, default=None):
    """Get a single setting value."""
    settings = load_settings()
    if default is None and key in DEFAULT_SETTINGS:
        default = DEFAULT_SETTINGS[key]
    return settings.get(key, default)


def set_setting(key, value):
    """Set a single setting value."""
    settings = load_settings()
    settings[key] = value
    save_settings(settings)


def get_data_dir():
    """Get the data directory from settings or return default."""
    data_dir = get_setting("data_dir")
    if data_dir and os.path.isdir(data_dir):
        return data_dir
    return None


def set_data_dir(path):
    """Set the data directory in settings."""
    set_setting("data_dir", path)


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
DOWNLOADS_DIR = os.path.join(DATA_DIR, "downloads")

# Collection file location - default in user's home directory, but configurable via settings
_DEFAULT_COLLECTION_FILE = os.path.join(os.path.expanduser("~"), ".cardwatcher_collection.json")
_saved_collection = get_setting("collection_file")
COLLECTION_FILE = _saved_collection if _saved_collection else _DEFAULT_COLLECTION_FILE


def update_paths(data_dir):
    """Update all path constants with a new data directory.
    Note: COLLECTION_FILE is NOT updated - it stays in user's home directory."""
    global DATA_DIR, PAGES_DIR, ARCHIVE_DIR, IMAGES_DIR, CHANGES_DIR, DOWNLOADS_DIR
    DATA_DIR = data_dir
    PAGES_DIR = os.path.join(DATA_DIR, "pages")
    ARCHIVE_DIR = os.path.join(DATA_DIR, "archive")
    IMAGES_DIR = os.path.join(DATA_DIR, "images")
    CHANGES_DIR = os.path.join(DATA_DIR, "changes")
    DOWNLOADS_DIR = os.path.join(DATA_DIR, "downloads")
