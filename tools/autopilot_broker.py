"""Local paper broker for TRaid Autopilot — pure account math, no network.

The account is a plain dict persisted as JSON. All money rounds to cents.
Rails live in autopilot_rails.py; this module only mutates state and never
decides whether a trade is *allowed* (beyond physical impossibility).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _cents(x):
    return round(float(x), 2)


def new_account(starting_capital=5000.0):
    return {
        "starting_capital": _cents(starting_capital),
        "cash": _cents(starting_capital),
        "positions": [],   # [{"ticker","shares","avg_cost"}]
        "halted": False,
    }


def _find(account, ticker):
    for p in account["positions"]:
        if p["ticker"] == ticker:
            return p
    return None


def position_shares(account, ticker):
    p = _find(account, ticker)
    return p["shares"] if p else 0


def apply_fill(account, side, ticker, shares, price):
    import copy
    a = copy.deepcopy(account)
    shares = float(shares)
    price = float(price)
    if shares <= 0:
        raise ValueError("shares must be positive")
    pos = _find(a, ticker)
    if side == "buy":
        cost = shares * price
        if cost > a["cash"] + 1e-9:
            raise ValueError(f"insufficient cash: need {cost}, have {a['cash']}")
        a["cash"] = _cents(a["cash"] - cost)
        if pos:
            total = pos["shares"] + shares
            pos["avg_cost"] = _cents((pos["shares"] * pos["avg_cost"] + cost) / total)
            pos["shares"] = total
        else:
            a["positions"].append({"ticker": ticker, "shares": shares, "avg_cost": _cents(price)})
    elif side == "sell":
        if not pos or shares > pos["shares"] + 1e-9:
            raise ValueError(f"cannot sell {shares} {ticker}: holding {position_shares(a, ticker)}")
        a["cash"] = _cents(a["cash"] + shares * price)
        pos["shares"] -= shares
        if pos["shares"] <= 1e-9:
            a["positions"] = [p for p in a["positions"] if p["ticker"] != ticker]
    else:
        raise ValueError(f"unknown side: {side}")
    # normalise whole-share counts to int when clean
    for p in a["positions"]:
        if abs(p["shares"] - round(p["shares"])) < 1e-9:
            p["shares"] = int(round(p["shares"]))
    return a


def mark_to_market(account, prices):
    positions = []
    invested = 0.0
    for p in account["positions"]:
        price = float(prices.get(p["ticker"], p["avg_cost"]))
        value = p["shares"] * price
        cost = p["shares"] * p["avg_cost"]
        invested += value
        positions.append({
            "ticker": p["ticker"], "shares": p["shares"], "avg_cost": _cents(p["avg_cost"]),
            "price": _cents(price), "value": _cents(value),
            "pnl_abs": _cents(value - cost),
            "pnl_pct": round((price / p["avg_cost"] - 1) * 100, 2) if p["avg_cost"] else 0.0,
        })
    total = account["cash"] + invested
    start = account["starting_capital"]
    return {
        "cash": _cents(account["cash"]),
        "invested": _cents(invested),
        "total_value": _cents(total),
        "pnl_abs": _cents(total - start),
        "pnl_pct": round((total / start - 1) * 100, 2) if start else 0.0,
        "positions": positions,
    }


def load_account(path):
    with open(path) as f:
        return json.load(f)


def save_account(account, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(account, f, indent=2)
