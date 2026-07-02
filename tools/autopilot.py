"""TRaid Autopilot runner CLI.

Verbs:
  prepare              -> print a JSON market snapshot + today's brain model
  execute '<orders>'   -> validate orders through rails, fill, rewrite status.txt
  brain-model          -> print today's model id (for the run wrapper)

Money-logic lives in the pure modules (broker/rails/status); this file wires
them to live data and the filesystem.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.autopilot_broker import new_account, load_account, save_account, position_shares, mark_to_market
from tools.autopilot_clock import is_market_open, brain_model_for, brain_label
from tools.autopilot_cache import get_fundamentals
from tools.autopilot_news import headlines
from tools.autopilot_rails import is_halted, validate_order
from tools.autopilot_status import render_status

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DIR = os.path.join(_ROOT, "data", "autopilot")
ACCOUNT_PATH = os.path.join(_DIR, "account.json")
TRADES_PATH = os.path.join(_DIR, "trades.jsonl")
STATUS_PATH = os.path.join(_DIR, "status.txt")
FUND_CACHE_PATH = os.path.join(_DIR, "fundamentals_cache.json")
WATCHLIST_PATH = os.path.join(_ROOT, "watchlist.json")
_NY = ZoneInfo("America/New_York")
_ART = ZoneInfo("America/Argentina/Buenos_Aires")


def load_watchlist(path=WATCHLIST_PATH):
    with open(path) as f:
        return json.load(f)


def _price_quote(ticker):
    from tools.market import quote
    q = quote(ticker)
    return q.get("price") if isinstance(q, dict) else None


def _indicators(ticker):
    from tools.indicators import analyze
    return analyze(ticker, period="6mo")


def build_snapshot(now_utc, watchlist, account, deps):
    ny_date = now_utc.astimezone(_NY).date()
    model = brain_model_for(ny_date)
    prices = {}
    tickers = {}
    for t in watchlist:
        price = deps["price"](t)
        if price is not None:
            prices[t] = price
        tickers[t] = {
            "price": price,
            "position": position_shares(account, t),
            "technicals": deps["indicators"](t),
            "fundamentals": deps["fundamentals"](t),
            "news": deps["news"](t),
        }
    return {
        "as_of": now_utc.isoformat(),
        "market_open": is_market_open(now_utc),
        "brain_model": model,
        "brain_label": brain_label(model),
        "account": mark_to_market(account, prices),
        "tickers": tickers,
    }


def _load_or_create_account():
    if os.path.exists(ACCOUNT_PATH):
        return load_account(ACCOUNT_PATH)
    acct = new_account(5000.0)
    save_account(acct, ACCOUNT_PATH)
    return acct


def cmd_prepare():
    now = datetime.now(timezone.utc)
    watchlist = load_watchlist()
    account = _load_or_create_account()
    today_iso = now.astimezone(_NY).date().isoformat()
    deps = {
        "indicators": _indicators,
        "fundamentals": lambda t: get_fundamentals(t, today_iso, FUND_CACHE_PATH),
        "news": headlines,
        "price": _price_quote,
    }
    return build_snapshot(now, watchlist, account, deps)


def _fmt_art(now_utc):
    return now_utc.astimezone(_ART).strftime("%Y-%m-%d %H:%M ART")


def _next_run_art(now_utc):
    return (now_utc + timedelta(hours=1)).astimezone(_ART).strftime("%Y-%m-%d %H:%M ART")


def execute_orders(orders, account, prices, watchlist, now_utc):
    market_open = is_market_open(now_utc)
    halted = is_halted(account, prices)
    acct = account
    results = []
    for order in orders:
        ok, reason = validate_order(order, acct, prices, watchlist, market_open, halted)
        price = prices.get(order.get("ticker"))
        if ok:
            from tools.autopilot_broker import apply_fill
            acct = apply_fill(acct, order["side"], order["ticker"], order["shares"], price)
            halted = is_halted(acct, prices)  # re-check after each fill
        results.append({"order": order, "filled": ok, "reason": reason, "price": price})
    return acct, results


def _append_trades(results, now_utc):
    os.makedirs(_DIR, exist_ok=True)
    stamp = now_utc.astimezone(_ART).strftime("%H:%M")
    moves = []
    with open(TRADES_PATH, "a") as f:
        for r in results:
            o = r["order"]
            rec = {"at": now_utc.isoformat(), "side": o.get("side"), "ticker": o.get("ticker"),
                   "shares": o.get("shares"), "price": r["price"], "filled": r["filled"],
                   "reason": r.get("order", {}).get("reason", ""), "rail": r["reason"]}
            f.write(json.dumps(rec) + "\n")
            if r["filled"]:
                why = o.get("reason", "")
                moves.append(f"{stamp}  {o['side'].upper()} {o['shares']} {o['ticker']} @ ${r['price']:.2f}"
                             + (f" — {why}" if why else ""))
    if not any(r["filled"] for r in results):
        moves.append(f"{stamp}  HOLD everything")
    return moves


def cmd_execute(orders_json):
    orders = json.loads(orders_json) if isinstance(orders_json, str) else orders_json
    now = datetime.now(timezone.utc)
    account = _load_or_create_account()
    watchlist = load_watchlist()
    prices = {}
    for t in set(watchlist) | {o.get("ticker") for o in orders}:
        px = _price_quote(t)
        if px is not None:
            prices[t] = px
    acct, results = execute_orders(orders, account, prices, watchlist, now)
    acct["halted"] = is_halted(acct, prices)
    save_account(acct, ACCOUNT_PATH)
    moves = _append_trades(results, now)
    marked = mark_to_market(acct, prices)
    model = brain_model_for(now.astimezone(_NY).date())
    status = render_status(marked, brain_label(model), _fmt_art(now), _next_run_art(now),
                           list(reversed(moves)), halted=acct["halted"])
    os.makedirs(_DIR, exist_ok=True)
    with open(STATUS_PATH, "w") as f:
        f.write(status)
    return {"filled": sum(1 for r in results if r["filled"]), "results": results}


def cmd_brain_model():
    return brain_model_for(datetime.now(timezone.utc).astimezone(_NY).date())


def main(argv=None):
    p = argparse.ArgumentParser(description="TRaid Autopilot runner")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare")
    ex = sub.add_parser("execute")
    ex.add_argument("orders", help="JSON list of orders")
    sub.add_parser("brain-model")
    args = p.parse_args(argv)
    if args.cmd == "prepare":
        print(json.dumps(cmd_prepare(), indent=2, default=str))
    elif args.cmd == "execute":
        print(json.dumps(cmd_execute(args.orders), indent=2, default=str))
    elif args.cmd == "brain-model":
        print(cmd_brain_model())


if __name__ == "__main__":
    main()
