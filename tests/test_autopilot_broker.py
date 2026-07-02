import math
import pytest
from tools.autopilot_broker import (
    new_account, position_shares, apply_fill, mark_to_market,
    load_account, save_account,
)


def test_new_account_defaults():
    a = new_account()
    assert a["starting_capital"] == 5000.0
    assert a["cash"] == 5000.0
    assert a["positions"] == []
    assert a["halted"] is False


def test_buy_reduces_cash_and_opens_position():
    a = apply_fill(new_account(1000.0), "buy", "NVDA", 2, 100.0)
    assert a["cash"] == 800.0
    assert position_shares(a, "NVDA") == 2
    assert a["positions"][0]["avg_cost"] == 100.0


def test_buy_again_averages_cost():
    a = new_account(1000.0)
    a = apply_fill(a, "buy", "NVDA", 2, 100.0)   # 200
    a = apply_fill(a, "buy", "NVDA", 2, 200.0)   # 400
    assert position_shares(a, "NVDA") == 4
    assert a["positions"][0]["avg_cost"] == 150.0
    assert a["cash"] == 400.0


def test_sell_returns_cash_keeps_avg_cost_and_removes_when_flat():
    a = new_account(1000.0)
    a = apply_fill(a, "buy", "NVDA", 4, 100.0)   # cash 600
    a = apply_fill(a, "sell", "NVDA", 4, 120.0)  # cash 600+480
    assert a["cash"] == 1080.0
    assert position_shares(a, "NVDA") == 0
    assert a["positions"] == []


def test_buy_over_cash_raises():
    with pytest.raises(ValueError):
        apply_fill(new_account(100.0), "buy", "NVDA", 2, 100.0)


def test_oversell_raises():
    a = apply_fill(new_account(1000.0), "buy", "NVDA", 1, 100.0)
    with pytest.raises(ValueError):
        apply_fill(a, "sell", "NVDA", 2, 100.0)


def test_mark_to_market_pnl():
    a = new_account(1000.0)
    a = apply_fill(a, "buy", "NVDA", 4, 100.0)   # cash 600, cost 400
    m = mark_to_market(a, {"NVDA": 150.0})
    assert m["cash"] == 600.0
    assert m["invested"] == 600.0                 # 4 * 150
    assert m["total_value"] == 1200.0
    assert m["pnl_abs"] == 200.0
    assert m["pnl_pct"] == 20.0
    pos = m["positions"][0]
    assert pos["value"] == 600.0 and pos["pnl_pct"] == 50.0


def test_mark_to_market_missing_price_uses_cost():
    a = apply_fill(new_account(1000.0), "buy", "NVDA", 4, 100.0)
    m = mark_to_market(a, {})  # no price
    assert m["positions"][0]["price"] == 100.0
    assert m["pnl_abs"] == 0.0


def test_save_and_load_roundtrip(tmp_path):
    p = tmp_path / "account.json"
    a = apply_fill(new_account(1000.0), "buy", "NVDA", 1, 100.0)
    save_account(a, str(p))
    assert load_account(str(p)) == a
