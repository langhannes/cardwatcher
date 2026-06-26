"""Tests for app/watcherbase.py metric calculations."""
import time

from app.watcherbase import watcherbase
from tests.conftest import make_listing


class _FakePage:
    def __init__(self, listings):
        self.listings = listings


# --- calculate_price_average_time_weighted ----------------------------------

def test_time_weighted_empty():
    assert watcherbase.calculate_price_average_time_weighted([]) == 0.0


def test_time_weighted_equal_timestamps_is_mean():
    t = 1700000000.0
    result = watcherbase.calculate_price_average_time_weighted(
        [(10.0, t), (20.0, t)], reference_time=t)
    assert result == 15.0


def test_time_weighted_half_life_decay():
    now = 1700000000.0
    one_half_life_ago = now - 30 * 24 * 60 * 60
    # Recent sale weight 1.0, sale one half-life ago weight 0.5.
    # (10*1 + 20*0.5) / (1 + 0.5) = 20 / 1.5 = 13.333...
    result = watcherbase.calculate_price_average_time_weighted(
        [(10.0, now), (20.0, one_half_life_ago)],
        half_life_days=30, reference_time=now)
    assert result == 13.333333333333334


# --- calculate_historical_min -----------------------------------------------

def test_calculate_historical_min():
    now = time.time()
    day = 24 * 60 * 60
    listings = [
        # existed 30 days ago, active -> counts, price 50
        make_listing(seller="a", price=50.0, first_date=now - 30 * day, date=now),
        # only appeared 2 days ago -> not present at the 7-day cutoff
        make_listing(seller="b", price=5.0, first_date=now - 2 * day, date=now),
        # existed 60 days ago, active -> counts, price 20 (the minimum)
        make_listing(seller="c", price=20.0, first_date=now - 60 * day, date=now),
    ]
    result = watcherbase.calculate_historical_min(_FakePage(listings), days_ago=7)
    assert result == 20.0


def test_calculate_historical_min_no_data():
    assert watcherbase.calculate_historical_min(_FakePage([]), days_ago=7) is None


# --- calculate_market_prices ------------------------------------------------

def test_calculate_market_prices_blend_sold_floor():
    now = time.time()
    active = [make_listing(seller=f"ask{i}", price=p, quantity=1, ended=False)
              for i, p in enumerate([10.0, 11.0, 12.0, 13.0])]
    sold = [make_listing(seller=f"sold{i}", price=20.0, quantity=1, ended=True, date=now)
            for i in range(3)]

    result = watcherbase.calculate_market_prices(_FakePage(active + sold))

    assert result["language"] == "English"
    assert result["n_ask"] == 4
    assert result["n_sold"] == 3
    # transaction: time-weighted mean of three 20.0 sales at "now" -> 20.0
    assert result["transaction"] == 20.0
    # floor: 10th percentile of [10,11,12,13] -> 10.3
    assert result["floor"] == 10.3
    # blend: (0.6*20 + 0.4*10.3) = 16.12
    assert result["blend"] == 16.12


def test_calculate_market_prices_floor_only_when_no_sales():
    active = [make_listing(seller=f"ask{i}", price=p, quantity=1, ended=False)
              for i, p in enumerate([10.0, 11.0, 12.0, 13.0])]
    result = watcherbase.calculate_market_prices(_FakePage(active))
    assert result["transaction"] == 0.0
    assert result["blend"] == result["floor"] == 10.3


def test_floor_ignores_other_languages():
    # English is the dominant (most-supplied) language and sits ~100. A handful
    # of cheap Japanese asks must not drag the English floor down.
    english = [make_listing(seller=f"en{i}", price=p, quantity=1, ended=False)
               for i, p in enumerate([100.0, 102.0, 104.0, 106.0, 108.0])]
    japanese = [make_listing(seller=f"jp{i}", price=p, quantity=1, ended=False,
                             language="Japanese")
                for i, p in enumerate([55.0, 58.0])]
    result = watcherbase.calculate_market_prices(_FakePage(english + japanese))
    assert result["language"] == "English"
    assert result["floor"] >= 100.0


def test_pinned_language_does_not_fall_back_to_other_languages():
    # When a language is pinned but has no listings in the snapshot, the metric
    # is empty rather than silently borrowing another (cheaper) language.
    japanese = [make_listing(seller=f"jp{i}", price=p, quantity=1, ended=False,
                             language="Japanese")
                for i, p in enumerate([55.0, 58.0, 60.0])]
    result = watcherbase.calculate_market_prices(
        _FakePage(japanese), lang="English")
    assert result["floor"] == 0.0
    assert result["n_ask"] == 0


# --- dominant_language (priority by availability) ---------------------------

def test_dominant_language_prefers_english_even_when_outnumbered():
    # A Western card: English exists, so it wins regardless of Japanese supply.
    listings = ([make_listing(seller=f"jp{i}", language="Japanese")
                 for i in range(10)]
                + [make_listing(seller=f"en{i}", language="English")
                   for i in range(2)])
    assert watcherbase.dominant_language(listings) == "English"


def test_dominant_language_falls_through_to_japanese():
    # No English on offer -> Japanese (Japanese-origin card).
    listings = [make_listing(seller=f"jp{i}", language="Japanese")
                for i in range(4)]
    assert watcherbase.dominant_language(listings) == "Japanese"


def test_dominant_language_chinese_only():
    listings = [make_listing(seller=f"cn{i}", language="S-Chinese")
                for i in range(3)]
    assert watcherbase.dominant_language(listings) == "S-Chinese"


def test_dominant_language_ignores_single_stray():
    # One mislabeled English listing must not hijack a Japanese-only product.
    listings = ([make_listing(seller=f"jp{i}", language="Japanese")
                 for i in range(6)]
                + [make_listing(seller="stray", language="English")])
    assert watcherbase.dominant_language(listings) == "Japanese"


def test_dominant_language_non_priority_falls_back_to_supply():
    # Only Western non-English languages present -> most-supplied wins.
    listings = ([make_listing(seller=f"de{i}", language="German")
                 for i in range(3)]
                + [make_listing(seller="fr", language="French")])
    assert watcherbase.dominant_language(listings) == "German"


# --- calculate_all_period_averages (shape) ----------------------------------

def test_calculate_all_period_averages_shape():
    now = time.time()
    day = 24 * 60 * 60
    listings = [
        make_listing(seller="a", price=10.0, quantity=2, ended=False,
                     first_date=now - 200 * day, date=now),
        make_listing(seller="b", price=12.0, quantity=1, ended=False,
                     first_date=now - 200 * day, date=now),
        make_listing(seller="c", price=15.0, quantity=1, ended=True,
                     first_date=now - 200 * day, date=now - 10 * day),
    ]
    result = watcherbase.calculate_all_period_averages(_FakePage(listings))

    for key in ("current_avg", "current_ended_avg", "current_available",
                "current_min", "market"):
        assert key in result
    assert result["current_available"] == 3  # qty 2 + 1 active

    for period in ("1w", "1m", "2m", "6m"):
        assert period in result
        assert "market" in result[period]
        assert "blend" in result[period]["market"]
