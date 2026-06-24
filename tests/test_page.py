"""Tests for app/page.py — robust averaging and update_page matching logic."""
from app.page import Page
from tests.conftest import make_listing


# --- calculate_price_average_robust (IQR) -----------------------------------

def test_robust_average_empty():
    assert Page.calculate_price_average_robust([]) == 0.0


def test_robust_average_small_set_is_simple_mean():
    # Fewer than 4 points -> plain mean, no filtering.
    assert Page.calculate_price_average_robust([10.0, 20.0, 30.0]) == 20.0


def test_robust_average_zero_iqr_is_simple_mean():
    # All-equal quartiles -> IQR 0 -> falls back to plain mean (outlier kept).
    assert Page.calculate_price_average_robust([10, 10, 10, 10, 1000]) == 208.0


def test_robust_average_filters_outlier():
    # IQR>0: the 1000 sits outside the upper bound and is dropped.
    assert Page.calculate_price_average_robust([10, 12, 14, 16, 1000]) == 13.0


# --- update_page matching: continuing / relisted / ended --------------------

def _make_new_page(canonical, listings, price_average):
    page = Page()
    page.canonical_name = canonical
    page.card = "Card"
    page.set = "Set"
    page.image = "img.jpg"
    page.languages = ["English"]
    page.only_germany = False
    page.loadMoreButton = False
    page.listings = listings
    page.price_average = price_average
    return page


def test_update_page_continuing_relisted_and_ended():
    canonical = "Test_Card"

    # Existing (old) state.
    old = Page()
    old.canonical_name = canonical
    old.price_average = 10.0
    alice_old = make_listing(seller="alice", price=10.0, date=100.0, first_date=100.0)
    bob_old = make_listing(seller="bob", price=20.0, date=100.0, first_date=100.0)
    carol_old = make_listing(seller="carol", price=30.0, date=80.0, first_date=50.0,
                             ended=True)
    old.listings = [alice_old, bob_old, carol_old]

    # Incoming (new) data: alice's price changed, carol relisted, bob gone.
    alice_new = make_listing(seller="alice", price=12.0, date=200.0, first_date=200.0,
                             quantity=1)
    carol_new = make_listing(seller="carol", price=33.0, date=200.0, first_date=200.0,
                             quantity=1, comment="back again")
    new = _make_new_page(canonical, [alice_new, carol_new], price_average=15.0)

    old.update_page(new)

    by_seller = {l.seller.name: l for l in old.listings}

    # alice: continuing with a price change
    alice = by_seller["alice"]
    assert alice.new is False
    assert alice.ended is False
    assert alice.price == 12.0
    assert alice.price_is_new is True
    assert (10.0, 100.0) in alice.previous_prices
    assert alice.first_date == 100.0  # original first_date preserved

    # carol: relisted (was ended, reappeared)
    carol = by_seller["carol"]
    assert carol.new is False
    assert carol.ended is False
    assert carol.comment.startswith("RELISTED!")

    # bob: gone -> ended and counted as sold
    bob = by_seller["bob"]
    assert bob.ended is True

    assert old.sold == 1
    assert old.inserted == 1  # carol re-counted; alice was continuing
    assert old.price_change == 5.0  # 15.0 - 10.0
    assert old.price_average == 15.0


def test_update_page_marks_unchanged_listing_not_new():
    canonical = "Test_Card"
    old = Page()
    old.canonical_name = canonical
    old.listings = [make_listing(seller="alice", price=10.0, date=100.0, first_date=100.0)]

    alice_new = make_listing(seller="alice", price=10.0, date=200.0, first_date=200.0)
    new = _make_new_page(canonical, [alice_new], price_average=10.0)

    old.update_page(new)

    assert len(old.listings) == 1
    assert old.listings[0].new is False
    assert old.listings[0].price_is_new is False
    assert old.sold == 0
    assert old.inserted == 0
