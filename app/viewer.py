"""Lightweight data endpoints for the client-side dashboard/search views.

The dashboard and search grids are now rendered in the browser (static/viewer/*)
instead of server-side by build_dashboard/build_search. They read
changes/price_history.json plus this manifest. The manifest only needs each
card's canonical name and last-updated time, so it is built from a directory
listing + mtimes — no per-page JSON parsing, unlike the old build_search loop.
"""
import os
import app.config as config


def _entries(directory):
    out = []
    if os.path.isdir(directory):
        for f in sorted(os.listdir(directory)):
            if f.endswith(".json"):
                out.append({
                    "canonical": f[:-5],
                    "updated": os.path.getmtime(os.path.join(directory, f)),
                })
    return out


def build_manifest():
    """Active + archived card lists ({canonical, updated}) for the viewer JS.

    Reads config.PAGES_DIR / config.ARCHIVE_DIR dynamically so it always
    reflects the data dir chosen at startup (config.update_paths reassigns them).
    """
    return {
        "cards": _entries(config.PAGES_DIR),
        "archived": _entries(config.ARCHIVE_DIR),
    }
