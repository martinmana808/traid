"""Hard risk rails for TRaid Autopilot — enforced in code, not the prompt.

validate_order is the ONLY gate between an AI proposal and a real fill.
Long-only, no leverage, watchlist-only, <=40% per name, market-open, and a
-25% circuit breaker that blocks new buys.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.autopilot_broker import mark_to_market, position_shares

MAX_POSITION_PCT = 0.40
CIRCUIT_BREAKER_PCT = -25.0


def is_halted(account, prices):
    return mark_to_market(account, prices)["pnl_pct"] <= CIRCUIT_BREAKER_PCT


def validate_order(order, account, prices, watchlist, market_open, halted):
    side = order.get("side")
    ticker = order.get("ticker")
    shares = order.get("shares", 0)

    if not market_open:
        return False, "market closed — no fills"
    if ticker not in watchlist:
        return False, f"{ticker} not on watchlist"
    if side not in ("buy", "sell"):
        return False, f"invalid side {side!r}"
    try:
        shares = float(shares)
    except (TypeError, ValueError):
        return False, "shares not a number"
    if not math.isfinite(shares):
        return False, "shares not finite"
    if shares <= 0:
        return False, "shares must be positive"
    price = prices.get(ticker)
    if price is None or price <= 0:
        return False, f"no live price for {ticker}"

    if side == "sell":
        held = position_shares(account, ticker)
        if shares > held + 1e-9:
            return False, f"cannot sell {shares:g} {ticker} — hold {held:g} (long-only, no shorting)"
        return True, "ok"

    # side == buy
    if halted:
        return False, "circuit breaker halted — no new buys (down >=25%)"
    cost = shares * price
    if cost > account["cash"] + 1e-9:
        return False, f"insufficient cash — need ${cost:.2f}, have ${account['cash']:.2f} (no leverage)"
    marked = mark_to_market(account, prices)
    total = marked["total_value"]                       # a buy shifts cash->shares; total unchanged
    existing = next((p["value"] for p in marked["positions"] if p["ticker"] == ticker), 0.0)
    if total > 0 and (existing + cost) > MAX_POSITION_PCT * total + 1e-9:
        pct = (existing + cost) / total * 100
        return False, f"{ticker} would be {pct:.0f}% of account — over 40% cap"
    return True, "ok"
