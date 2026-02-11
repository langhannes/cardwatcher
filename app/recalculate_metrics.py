"""
Recalculates metrics from existing page JSON files.
Useful for populating new metrics (like current_min) without re-downloading pages.

Usage: python -m app.recalculate_metrics
"""

import os
import json
from app.page import Page
from app.watcherbase import watcherbase
from app.config import PAGES_DIR, CHANGES_DIR


def recalculate_all():
    """
    For each page in PAGES_DIR:
    1. Load the Page object
    2. Call calculate_all_period_averages()
    3. Store in price_history.json
    """
    # Load existing price_history.json
    price_history_path = os.path.join(CHANGES_DIR, "price_history.json")
    existing_history = {}
    if os.path.exists(price_history_path):
        try:
            with open(price_history_path, "r", encoding="utf-8") as f:
                existing_history = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load existing price_history.json: {e}")
            existing_history = {}

    # Get all page files
    page_files = [f for f in os.listdir(PAGES_DIR) if f.endswith('.json')]

    processed = 0
    errors = 0

    for page_file in page_files:
        canonical_name = page_file[:-5]  # Remove .json
        try:
            # Load page
            page = Page()
            page.canonical_name = canonical_name
            page.import_page(os.path.join(PAGES_DIR, page_file))

            # Calculate all metrics
            metrics = watcherbase.calculate_all_period_averages(page)

            # Preserve last_download data if it exists, add ended_avg if missing
            if canonical_name in existing_history and 'last_download' in existing_history[canonical_name]:
                last_download = existing_history[canonical_name]['last_download']
                # Add ended_avg if not present (for existing data before this feature)
                if 'ended_avg' not in last_download:
                    last_download['ended_avg'] = metrics.get('current_ended_avg', 0)
                    last_download['ended_avg_change'] = 0  # No change data for old records
                metrics['last_download'] = last_download

            # Update history
            existing_history[canonical_name] = metrics

            processed += 1
            print(f"Processed: {canonical_name} (min: {metrics.get('current_min', 0)}€)")

        except Exception as e:
            errors += 1
            print(f"Error processing {page_file}: {e}")

    # Save updated price_history.json
    with open(price_history_path, "w", encoding="utf-8") as f:
        json.dump(existing_history, f, indent=2)

    print(f"\n=== Summary ===")
    print(f"Processed: {processed} pages")
    print(f"Errors: {errors}")
    print(f"Saved to: {price_history_path}")


if __name__ == "__main__":
    recalculate_all()
