import os

# Data directory: sibling "cardwatcher-data" folder next to the application directory
_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_APP_ROOT, "..", "cardwatcher-data")

PAGES_DIR = os.path.join(DATA_DIR, "pages")
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive")
IMAGES_DIR = os.path.join(DATA_DIR, "images")
CHANGES_DIR = os.path.join(DATA_DIR, "changes")
