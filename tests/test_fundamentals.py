from unittest.mock import MagicMock, patch

from tools.fundamentals import (
    compute_peg, classify_pe, classify_growth, classify_margin, classify_health,
    analyze,
)


def test_compute_peg_basic():
    assert compute_peg(30, 30) == 1.0


def test_compute_peg_none_without_growth():
    assert compute_peg(33, None) is None
    assert compute_peg(33, 0) is None
    assert compute_peg(33, -5) is None


def test_compute_peg_none_without_pe():
    assert compute_peg(None, 20) is None


def test_classify_pe_buckets():
    assert classify_pe(None)[0] == "n/a"
    assert classify_pe(12)[0] == "low"
    assert classify_pe(20)[0] == "moderate"
    assert classify_pe(33)[0] == "elevated"
    assert classify_pe(120)[0] == "high"


def test_classify_growth_buckets():
    assert classify_growth(None)[0] == "n/a"
    assert classify_growth(-3)[0] == "shrinking"
    assert classify_growth(3)[0] == "slow"
    assert classify_growth(12)[0] == "solid"
    assert classify_growth(40)[0] == "strong"


def test_classify_margin_buckets():
    assert classify_margin(None)[0] == "n/a"
    assert classify_margin(-5)[0] == "unprofitable"
    assert classify_margin(3)[0] == "thin"
    assert classify_margin(12)[0] == "healthy"
    assert classify_margin(35)[0] == "high"


def test_classify_health_buckets():
    assert classify_health(None)[0] == "n/a"
    assert classify_health(0.3)[0] == "low debt"
    assert classify_health(1.0)[0] == "moderate debt"
    assert classify_health(3.0)[0] == "high debt"


# --- snapshot fields (no network) ------------------------------------------

_FAKE_INFO = {
    "shortName": "ACME Corp",
    "sector": "Technology",
    "trailingPE": 25.0,
    "forwardPE": 20.0,
    "revenueGrowth": 0.12,
    "earningsGrowth": 0.15,
    "profitMargins": 0.20,
    "returnOnEquity": 0.18,
    "debtToEquity": 44.5,
    "freeCashflow": 1_000_000_000,
    "totalCash": 500_000_000,
    "totalDebt": 200_000_000,
    "trailingPegRatio": None,
    # snapshot fields
    "marketCap": 1_500_000_000_000,
    "averageVolume": 25_000_000,
    "dividendYield": 0.005,
    "earningsTimestamp": 1_750_000_000,
    "fiftyTwoWeekHigh": 145.67,
    "fiftyTwoWeekLow": 89.12,
    "recommendationKey": "buy",
    "targetMeanPrice": 160.0,
    "numberOfAnalystOpinions": 42,
}


def _make_mock_yf(info):
    ticker_mock = MagicMock()
    ticker_mock.info = info
    yf_mock = MagicMock()
    yf_mock.Ticker.return_value = ticker_mock
    return yf_mock


def test_analyze_snapshot_fields_populated():
    with patch.dict("sys.modules", {"yfinance": _make_mock_yf(_FAKE_INFO)}):
        result = analyze("ACME")

    snap = result["snapshot"]
    assert snap["market_cap"] == 1_500_000_000_000
    assert snap["avg_volume"] == 25_000_000
    assert snap["dividend_yield"] == 0.5           # _pct(0.005)
    assert snap["next_earnings"] == 1_750_000_000
    assert snap["week52_high"] == 145.67
    assert snap["week52_low"] == 89.12
    assert snap["analyst_rating"] == "buy"
    assert snap["analyst_target"] == 160.0
    assert snap["analyst_count"] == 42


def test_analyze_snapshot_missing_fields_are_none():
    sparse_info = {k: v for k, v in _FAKE_INFO.items()
                   if k not in {"marketCap", "dividendYield", "fiftyTwoWeekHigh",
                                "recommendationKey", "targetMeanPrice", "numberOfAnalystOpinions"}}
    with patch.dict("sys.modules", {"yfinance": _make_mock_yf(sparse_info)}):
        result = analyze("ACME")

    snap = result["snapshot"]
    assert snap["market_cap"] is None
    assert snap["dividend_yield"] is None
    assert snap["week52_high"] is None
    assert snap["analyst_rating"] is None
    assert snap["analyst_target"] is None
    assert snap["analyst_count"] is None
    # fields that ARE present should still work
    assert snap["avg_volume"] == 25_000_000


def test_analyze_snapshot_avg_volume_fallback():
    """averageVolume missing → falls back to averageVolume10days."""
    info = {**_FAKE_INFO}
    del info["averageVolume"]
    info["averageVolume10days"] = 18_000_000
    with patch.dict("sys.modules", {"yfinance": _make_mock_yf(info)}):
        result = analyze("ACME")

    assert result["snapshot"]["avg_volume"] == 18_000_000
