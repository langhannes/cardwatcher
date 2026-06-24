"""Tests for app/listing.py — tooltip fallback, row parsing, JSON round-trip."""
from bs4 import BeautifulSoup

from app.listing import Listing, tooltip_label
from tests.conftest import make_listing


# --- tooltip_label fallbacks ------------------------------------------------

def _span(html):
    return BeautifulSoup(html, "html.parser").find("span")


def test_tooltip_label_none_tag():
    assert tooltip_label(None) is None


def test_tooltip_label_prefers_aria_label():
    tag = _span('<span aria-label="A" title="B" data-bs-original-title="C"></span>')
    assert tooltip_label(tag) == "A"


def test_tooltip_label_falls_back_to_title():
    # Server-rendered case: only `title` is present (no aria-label yet).
    tag = _span('<span title="Artikelstandort: Deutschland"></span>')
    assert tooltip_label(tag) == "Artikelstandort: Deutschland"


def test_tooltip_label_falls_back_to_data_bs_original_title():
    tag = _span('<span data-bs-original-title="Englisch"></span>')
    assert tooltip_label(tag) == "Englisch"


def test_tooltip_label_missing_returns_none():
    tag = _span("<span></span>")
    assert tooltip_label(tag) is None


# --- parse_from_row ---------------------------------------------------------

def _row(html, row_id):
    return BeautifulSoup(html, "html.parser").find(id=row_id)


def test_parse_from_row_server_rendered(listing_rows_html):
    """Row with title-only tooltips must parse (the aria-label regression)."""
    listing = Listing()
    listing.parse_from_row(_row(listing_rows_html, "row-server-rendered"))

    assert listing.seller.name == "GermanSeller"
    assert listing.seller.country == "Item location: Germany"
    assert listing.language == "English"
    assert listing.condition == "NM"
    assert listing.comment == "near mint. ships fast"  # comma normalized to '.'
    assert listing.price == 12.5
    assert listing.quantity == 3
    assert listing.first_ed == 0
    assert listing.reverse_holo == 0


def test_parse_from_row_post_js_with_markers(listing_rows_html):
    listing = Listing()
    listing.parse_from_row(_row(listing_rows_html, "row-post-js"))

    assert listing.seller.name == "JpnSeller"
    assert listing.seller.country == "Item location: Japan"
    assert listing.language == "Japanese"
    assert listing.condition == "EX"
    assert listing.price == 1499.0
    assert listing.quantity == 1
    assert listing.first_ed == 1
    assert listing.reverse_holo == 1


# --- to_json / from_json round-trip -----------------------------------------

def test_to_json_from_json_round_trip():
    original = make_listing(
        seller="alice", country="Item location: Germany", language="English",
        condition="NM", price=42.5, quantity=2, date=1700000000.0,
        first_date=1690000000.0, ended=False, first_ed=1, reverse_holo=0,
        archived=True, comment="some comment",
        previous_prices=[(40.0, 1680000000.0), (45.0, 1685000000.0)],
    )
    original.canonical_name = "Some_Card"
    original.last_date = 1699000000.0
    original.price_is_new = True
    original.quantity_change = -1
    original.previous_quantities = [(3, 1680000000.0)]

    restored = Listing()
    restored.from_json(original.to_json())

    assert restored.seller.name == "alice"
    assert restored.seller.country == "Item location: Germany"
    assert restored.canonical_name == "Some_Card"
    assert restored.language == "English"
    assert restored.condition == "NM"
    assert restored.price == 42.5
    assert restored.quantity == 2
    assert restored.date == 1700000000.0
    assert restored.first_date == 1690000000.0
    assert restored.ended is False
    assert restored.first_ed == 1
    assert restored.reverse_holo == 0
    assert restored.archived is True
    assert restored.comment == "some comment"
    assert restored.price_is_new is True
    assert restored.quantity_change == -1
    assert restored.previous_prices == [(40.0, 1680000000.0), (45.0, 1685000000.0)]
    assert restored.previous_quantities == [(3, 1680000000.0)]
