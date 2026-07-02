from tools.autopilot_broker import new_account, apply_fill
from tools.autopilot_rails import is_halted, validate_order

WL = ["NVDA", "META"]


def _acct():
    return new_account(1000.0)


def test_market_closed_rejects():
    ok, why = validate_order({"side": "buy", "ticker": "NVDA", "shares": 1},
                             _acct(), {"NVDA": 100.0}, WL, market_open=False, halted=False)
    assert not ok and "closed" in why.lower()


def test_off_watchlist_rejects():
    ok, why = validate_order({"side": "buy", "ticker": "TSLA", "shares": 1},
                             _acct(), {"TSLA": 100.0}, WL, market_open=True, halted=False)
    assert not ok and "watchlist" in why.lower()


def test_bad_shares_rejects():
    ok, why = validate_order({"side": "buy", "ticker": "NVDA", "shares": 0},
                             _acct(), {"NVDA": 100.0}, WL, market_open=True, halted=False)
    assert not ok


def test_leverage_rejects():
    ok, why = validate_order({"side": "buy", "ticker": "NVDA", "shares": 20},
                             _acct(), {"NVDA": 100.0}, WL, market_open=True, halted=False)
    assert not ok and "cash" in why.lower()


def test_over_40pct_rejects():
    # $1000 account, buying $500 of one name = 50% > 40%
    ok, why = validate_order({"side": "buy", "ticker": "NVDA", "shares": 5},
                             _acct(), {"NVDA": 100.0}, WL, market_open=True, halted=False)
    assert not ok and "40" in why


def test_within_40pct_and_cash_ok():
    ok, why = validate_order({"side": "buy", "ticker": "NVDA", "shares": 3},
                             _acct(), {"NVDA": 100.0}, WL, market_open=True, halted=False)
    assert ok


def test_halted_blocks_buys_but_allows_sells():
    a = apply_fill(_acct(), "buy", "NVDA", 3, 100.0)
    buy_ok, _ = validate_order({"side": "buy", "ticker": "META", "shares": 1},
                               a, {"NVDA": 100.0, "META": 100.0}, WL, market_open=True, halted=True)
    sell_ok, _ = validate_order({"side": "sell", "ticker": "NVDA", "shares": 1},
                                a, {"NVDA": 100.0}, WL, market_open=True, halted=True)
    assert not buy_ok and sell_ok


def test_short_sell_rejects():
    ok, why = validate_order({"side": "sell", "ticker": "NVDA", "shares": 1},
                             _acct(), {"NVDA": 100.0}, WL, market_open=True, halted=False)
    assert not ok and ("hold" in why.lower() or "own" in why.lower())


def test_is_halted_trips_at_minus_25():
    a = apply_fill(new_account(1000.0), "buy", "NVDA", 10, 100.0)  # all-in, cost 1000
    assert is_halted(a, {"NVDA": 74.0}) is True    # -26%
    assert is_halted(a, {"NVDA": 80.0}) is False   # -20%
