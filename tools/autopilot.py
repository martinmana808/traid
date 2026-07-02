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


def main(argv=None):
    p = argparse.ArgumentParser(description="TRaid Autopilot runner")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare")
    args = p.parse_args(argv)
    if args.cmd == "prepare":
        print(json.dumps(cmd_prepare(), indent=2, default=str))


if __name__ == "__main__":
    main()
