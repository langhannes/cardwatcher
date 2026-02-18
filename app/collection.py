"""
Collection management for CardWatcher.
Handles personal card collection with price calculation.
"""
import os
import json
import time
from app.config import COLLECTION_FILE
from app.page import Page


class CollectionItem:
    """Represents a single card in the user's collection."""

    def __init__(self, canonical_name, condition="NM", language="English",
                 first_ed=0, reverse_holo=0, quantity=1, added_at=None):
        self.canonical_name = canonical_name
        self.condition = condition
        self.language = language
        self.first_ed = first_ed  # 0=no (unchecked), 2=yes (checked)
        self.reverse_holo = reverse_holo  # 0=no (unchecked), 2=yes (checked)
        self.quantity = quantity
        self.added_at = added_at or time.time()

    def to_dict(self):
        return {
            "canonical_name": self.canonical_name,
            "condition": self.condition,
            "language": self.language,
            "first_ed": self.first_ed,
            "reverse_holo": self.reverse_holo,
            "quantity": self.quantity,
            "added_at": self.added_at
        }

    @staticmethod
    def from_dict(data):
        return CollectionItem(
            canonical_name=data.get("canonical_name", ""),
            condition=data.get("condition", "NM"),
            language=data.get("language", "English"),
            first_ed=data.get("first_ed", 0),
            reverse_holo=data.get("reverse_holo", 0),
            quantity=data.get("quantity", 1),
            added_at=data.get("added_at")
        )


class Collection:
    """Manages the user's card collection."""

    def __init__(self):
        self.items = []
        self.updated_at = None

    def load(self):
        """Load collection from JSON file."""
        if os.path.exists(COLLECTION_FILE):
            try:
                with open(COLLECTION_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.items = [CollectionItem.from_dict(item) for item in data.get("items", [])]
                    self.updated_at = data.get("updated_at")
            except (json.JSONDecodeError, IOError):
                self.items = []
                self.updated_at = None
        return self

    def save(self):
        """Save collection to JSON file."""
        self.updated_at = time.time()
        data = {
            "items": [item.to_dict() for item in self.items],
            "updated_at": self.updated_at
        }
        with open(COLLECTION_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def add_item(self, canonical_name, condition="NM", language="English",
                 first_ed=0, reverse_holo=0, quantity=1):
        """Add or update an item in the collection."""
        # Check if item with same attributes exists
        for item in self.items:
            if (item.canonical_name == canonical_name and
                item.condition == condition and
                item.language == language and
                item.first_ed == first_ed and
                item.reverse_holo == reverse_holo):
                # Update quantity
                item.quantity += quantity
                self.save()
                return item

        # Add new item
        item = CollectionItem(
            canonical_name=canonical_name,
            condition=condition,
            language=language,
            first_ed=first_ed,
            reverse_holo=reverse_holo,
            quantity=quantity
        )
        self.items.append(item)
        self.save()
        return item

    def update_item(self, canonical_name, condition, language, first_ed, reverse_holo, quantity):
        """Update quantity of an existing item."""
        for item in self.items:
            if (item.canonical_name == canonical_name and
                item.condition == condition and
                item.language == language and
                item.first_ed == first_ed and
                item.reverse_holo == reverse_holo):
                if quantity <= 0:
                    self.items.remove(item)
                else:
                    item.quantity = quantity
                self.save()
                return True
        return False

    def remove_item(self, canonical_name, condition=None, language=None,
                    first_ed=None, reverse_holo=None):
        """Remove item(s) from collection."""
        removed = []
        for item in self.items[:]:
            if item.canonical_name != canonical_name:
                continue
            # If no filters specified, remove all entries for this card
            if condition is None:
                self.items.remove(item)
                removed.append(item)
            # Otherwise, match specific attributes
            elif (item.condition == condition and
                  item.language == language and
                  item.first_ed == first_ed and
                  item.reverse_holo == reverse_holo):
                self.items.remove(item)
                removed.append(item)

        if removed:
            self.save()
        return removed

    def get_items_for_page(self, canonical_name):
        """Get all collection items for a specific page/card."""
        return [item for item in self.items if item.canonical_name == canonical_name]

    def get_canonical_names(self):
        """Get set of all canonical names in collection."""
        return set(item.canonical_name for item in self.items)

    def to_dict(self):
        """Convert collection to dictionary."""
        return {
            "items": [item.to_dict() for item in self.items],
            "updated_at": self.updated_at
        }


def calculate_collection_price(page, condition, language, first_ed, reverse_holo):
    """
    Calculate realistic market price for a card with specific attributes.

    Priority order:
    1. Lowest available listing with exact match (condition, language, first_ed, reverse_holo)
    2. Latest ended listing with exact match
    3. Relaxed match: ignore first_ed, allow condition one grade better
    4. Overall average of available listings

    Args:
        page: Page object with listings
        condition: Card condition (MT, NM, EX, GD, LP, PL, PO)
        language: Card language
        first_ed: First edition flag (0=no/unchecked, 2=yes/checked)
        reverse_holo: Reverse holo flag (0=no/unchecked, 2=yes/checked)

    Returns:
        float: Calculated price, or 0 if no data
    """
    available = [l for l in page.listings if not l.ended]
    ended = [l for l in page.listings if l.ended]

    # Condition grades from best to worst
    condition_grades = ['MT', 'NM', 'EX', 'GD', 'LP', 'PL', 'PO']

    def is_condition_same_or_one_better(listing_condition, target_condition):
        """Check if listing condition is same or one grade better than target."""
        try:
            listing_idx = condition_grades.index(listing_condition)
            target_idx = condition_grades.index(target_condition)
            # Listing can be same grade or one better (lower index = better)
            return listing_idx >= target_idx - 1 and listing_idx <= target_idx
        except ValueError:
            return listing_condition == target_condition

    def matches(listing):
        """Check if listing matches the specified attributes."""
        if listing.condition != condition:
            return False
        if listing.language != language:
            return False
        # For first_ed and reverse_holo:
        # Collection/UI convention: 0=unchecked (not first ed), 2=checked (is first ed)
        # Listing convention: 0=no, 1=yes, 2=unknown
        # When collection checkbox is checked (2), match listing "yes" (1)
        # When collection checkbox is unchecked (0), match listing "no" (0)
        if first_ed == 2 and listing.first_ed != 1:  # Want first ed, listing must be first ed
            return False
        if first_ed == 0 and listing.first_ed != 0:  # Want non-first ed, listing must be non-first ed
            return False
        if reverse_holo == 2 and listing.reverse_holo != 1:  # Want reverse holo, listing must be reverse holo
            return False
        if reverse_holo == 0 and listing.reverse_holo != 0:  # Want non-reverse holo, listing must be non-reverse holo
            return False
        return True

    def matches_relaxed(listing):
        """Relaxed match: ignore first_ed, allow condition one grade better."""
        if not is_condition_same_or_one_better(listing.condition, condition):
            return False
        if listing.language != language:
            return False
        # Ignore first_ed in relaxed matching
        # Still check reverse_holo
        if reverse_holo == 2 and listing.reverse_holo != 1:
            return False
        if reverse_holo == 0 and listing.reverse_holo != 0:
            return False
        return True

    # 1. Exact match in available listings - use lowest price
    exact_available = [l for l in available if matches(l)]
    if exact_available:
        return min(l.price for l in exact_available)

    # 2. Exact match in ended listings - use most recent
    exact_ended = [l for l in ended if matches(l)]
    if exact_ended:
        latest = max(exact_ended, key=lambda l: l.last_date or l.date or 0)
        return latest.price

    # 3. Relaxed match: ignore first_ed, allow condition one grade better
    relaxed_available = [l for l in available if matches_relaxed(l)]
    if relaxed_available:
        return min(l.price for l in relaxed_available)

    # 4. Fallback to average of all available
    if available:
        return sum(l.price for l in available) / len(available)

    # 4. No data
    return 0


def calculate_collection_value(collection, pages_cache=None):
    """
    Calculate total value of the collection.

    Args:
        collection: Collection object
        pages_cache: Optional dict of {canonical_name: Page} to avoid reloading

    Returns:
        tuple: (total_value, item_count, items_with_prices)
            items_with_prices is list of (item, price) tuples
    """
    from app.config import PAGES_DIR, ARCHIVE_DIR

    total_value = 0.0
    item_count = 0
    items_with_prices = []

    pages_cache = pages_cache or {}

    for item in collection.items:
        # Load page if not in cache
        if item.canonical_name not in pages_cache:
            page = Page()
            # Try pages dir first, then archive
            page_path = os.path.join(PAGES_DIR, item.canonical_name + ".json")
            if not os.path.exists(page_path):
                page_path = os.path.join(ARCHIVE_DIR, item.canonical_name + ".json")
            if os.path.exists(page_path):
                page.import_page(page_path)
                pages_cache[item.canonical_name] = page
            else:
                pages_cache[item.canonical_name] = None

        page = pages_cache.get(item.canonical_name)
        if page is None:
            items_with_prices.append((item, 0))
            continue

        price = calculate_collection_price(
            page,
            item.condition,
            item.language,
            item.first_ed,
            item.reverse_holo
        )

        item_value = price * item.quantity
        total_value += item_value
        item_count += item.quantity
        items_with_prices.append((item, price))

    return total_value, item_count, items_with_prices
