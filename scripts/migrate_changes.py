"""
One-time migration script to consolidate changes files.
Merges changes.txt and price_changes.txt into price_history.json.

Creates backups of old files before migration.

Usage: python scripts/migrate_changes.py
"""

import os
import sys
import json
import shutil

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import CHANGES_DIR


def parse_changes_txt(filepath):
    """Parse changes.txt format: 'name inserted/sold'"""
    result = {}
    if not os.path.exists(filepath):
        return result

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f.readlines():
            line = line.strip()
            if not line or " " not in line:
                continue
            parts = line.split(" ")
            if len(parts) < 2:
                continue
            name = parts[0]
            values = parts[1].split("/")
            if len(values) >= 2:
                result[name] = {
                    "inserted": int(values[0]),
                    "sold": int(values[1])
                }
    return result


def parse_price_changes_txt(filepath):
    """Parse price_changes.txt format: 'name avg/change'"""
    result = {}
    if not os.path.exists(filepath):
        return result

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f.readlines():
            line = line.strip()
            if not line or " " not in line:
                continue
            parts = line.split(" ")
            if len(parts) < 2:
                continue
            name = parts[0]
            values = parts[1].split("/")
            if len(values) >= 2:
                result[name] = {
                    "avg": float(values[0]),
                    "avg_change": float(values[1])
                }
    return result


def migrate():
    """
    Migrate changes.txt and price_changes.txt into price_history.json.

    1. Load existing price_history.json
    2. Parse changes.txt -> extract inserted/sold per page
    3. Parse price_changes.txt -> extract avg/change per page
    4. Add "last_download" section to each page
    5. Backup old files
    6. Save updated price_history.json
    """

    changes_txt_path = os.path.join(CHANGES_DIR, "changes.txt")
    price_changes_txt_path = os.path.join(CHANGES_DIR, "price_changes.txt")
    price_history_path = os.path.join(CHANGES_DIR, "price_history.json")
    backup_dir = os.path.join(CHANGES_DIR, "backup")

    print("=== Migration: Consolidate Changes Storage ===\n")

    # Step 1: Load existing price_history.json
    print("Loading price_history.json...")
    price_history = {}
    if os.path.exists(price_history_path):
        with open(price_history_path, "r", encoding="utf-8") as f:
            price_history = json.load(f)
        print(f"  Loaded {len(price_history)} pages")
    else:
        print("  No existing price_history.json found")

    # Step 2: Parse changes.txt
    print("\nParsing changes.txt...")
    changes_data = parse_changes_txt(changes_txt_path)
    print(f"  Found {len(changes_data)} entries")

    # Step 3: Parse price_changes.txt
    print("\nParsing price_changes.txt...")
    price_changes_data = parse_price_changes_txt(price_changes_txt_path)
    print(f"  Found {len(price_changes_data)} entries")

    # Step 4: Merge into price_history with last_download section
    print("\nMerging data...")
    updated = 0
    created = 0

    # Get all unique page names
    all_pages = set(price_history.keys()) | set(changes_data.keys()) | set(price_changes_data.keys())

    for page_name in all_pages:
        # Initialize page entry if it doesn't exist
        if page_name not in price_history:
            price_history[page_name] = {}
            created += 1

        # Build last_download section
        last_download = {}

        # Add changes data (inserted/sold)
        if page_name in changes_data:
            last_download["inserted"] = changes_data[page_name]["inserted"]
            last_download["sold"] = changes_data[page_name]["sold"]

        # Add price changes data (avg/change)
        if page_name in price_changes_data:
            last_download["avg"] = price_changes_data[page_name]["avg"]
            last_download["avg_change"] = price_changes_data[page_name]["avg_change"]

        # Only add last_download if we have data
        if last_download:
            price_history[page_name]["last_download"] = last_download
            updated += 1

    print(f"  Updated: {updated} pages")
    print(f"  Created: {created} new entries")

    # Step 5: Create backups
    print("\nCreating backups...")
    os.makedirs(backup_dir, exist_ok=True)

    if os.path.exists(changes_txt_path):
        backup_path = os.path.join(backup_dir, "changes.txt")
        shutil.copy2(changes_txt_path, backup_path)
        print(f"  Backed up: changes.txt")

    if os.path.exists(price_changes_txt_path):
        backup_path = os.path.join(backup_dir, "price_changes.txt")
        shutil.copy2(price_changes_txt_path, backup_path)
        print(f"  Backed up: price_changes.txt")

    # Also backup the original price_history.json
    if os.path.exists(price_history_path):
        backup_path = os.path.join(backup_dir, "price_history.json.bak")
        shutil.copy2(price_history_path, backup_path)
        print(f"  Backed up: price_history.json")

    # Step 6: Save updated price_history.json
    print("\nSaving updated price_history.json...")
    with open(price_history_path, "w", encoding="utf-8") as f:
        json.dump(price_history, f, indent=2)
    print(f"  Saved {len(price_history)} pages")

    # Step 7: Remove old txt files (optional - uncomment to delete)
    print("\nCleaning up old files...")
    if os.path.exists(changes_txt_path):
        os.remove(changes_txt_path)
        print(f"  Removed: changes.txt")
    if os.path.exists(price_changes_txt_path):
        os.remove(price_changes_txt_path)
        print(f"  Removed: price_changes.txt")

    print("\n=== Migration Complete ===")
    print(f"Backups saved to: {backup_dir}")
    print(f"All data now in: {price_history_path}")


if __name__ == "__main__":
    migrate()
