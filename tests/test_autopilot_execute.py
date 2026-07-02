from datetime import datetime, timezone
from tools.autopilot_broker import new_account
from tools.autopilot import execute_orders

OPEN_UTC = datetime(2026, 7, 6, 14, 0, tzinfo=timezone.utc)
WL = ["NVDA", "META"]
PRICES = {"NVDA": 100.0, "META": 200.0}


def test_valid_buy_fills_and_updates_cash():
    orders = [{"side": "buy", "ticker": "NVDA", "shares": 3}]
    acct, results = execute_orders(orders, new_account(5000.0), PRICES, WL, OPEN_UTC)
    assert results[0]["filled"] is True
    assert acct["cash"] == 4700.0


def test_off_watchlist_rejected_not_filled():
    orders = [{"side": "buy", "ticker": "TSLA", "shares": 1}]
    acct, results = execute_orders(orders, new_account(5000.0), {"TSLA": 100.0}, WL, OPEN_UTC)
    assert results[0]["filled"] is False
    assert "watchlist" in results[0]["reason"].lower()
    assert acct["cash"] == 5000.0


def test_over_40pct_rejected():
    orders = [{"side": "buy", "ticker": "NVDA", "shares": 30}]  # $3000 of $5000 = 60%
    acct, results = execute_orders(orders, new_account(5000.0), PRICES, WL, OPEN_UTC)
    assert results[0]["filled"] is False
    assert acct["cash"] == 5000.0


def test_market_closed_fills_nothing():
    closed = datetime(2026, 7, 6, 21, 0, tzinfo=timezone.utc)
    orders = [{"side": "buy", "ticker": "NVDA", "shares": 1}]
    acct, results = execute_orders(orders, new_account(5000.0), PRICES, WL, closed)
    assert results[0]["filled"] is False
    assert acct["cash"] == 5000.0
