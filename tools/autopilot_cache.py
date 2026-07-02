"""Daily fundamentals cache for TRaid Autopilot.

Fundamentals are quarterly data — pointless to refetch every hour. Cache them
per NY date; a new date wipes the cache and refetches on demand.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _default_analyze(ticker):
    from tools.fundamentals import analyze
    return analyze(ticker)


def _load(cache_path, today_iso):
    try:
        with open(cache_path) as f:
            data = json.load(f)
        if data.get("date") == today_iso and isinstance(data.get("tickers"), dict):
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {"date": today_iso, "tickers": {}}


def get_fundamentals(ticker, today_iso, cache_path, _analyze=None):
    analyze = _analyze or _default_analyze
    data = _load(cache_path, today_iso)
    if ticker not in data["tickers"]:
        data["tickers"][ticker] = analyze(ticker)
        os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(data, f, indent=2)
    return data["tickers"][ticker]
