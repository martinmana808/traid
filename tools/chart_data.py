"""Builds chart-ready series dicts from OHLCV bars (Phase 7 — interactive charts).

Network-free core: `series_from_bars` reuses the indicator math from
`tools.indicators` and support/resistance from `tools.patterns`, and shapes the
result for TradingView lightweight-charts. `build_chart_data` is the thin
yfinance-backed wrapper.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.indicators import rsi, macd, bollinger, stochastic, atr  # noqa: E402
from tools.patterns import support_resistance  # noqa: E402
from tools.market import history, normalize_ticker  # noqa: E402
from tools.fundamentals import analyze as fundamentals_analyze  # noqa: E402


def _line(dates, series):
    """Zip dates with a pandas Series into one point per bar. Warm-up (NaN) bars
    become whitespace points ({time} only) so every series shares the same time
    domain as the candles — required for exact cross-pane axis sync."""
    out = []
    for d, v in zip(dates, series.tolist()):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            out.append({"time": d})
        else:
            out.append({"time": d, "value": round(float(v), 4)})
    return out


def series_from_bars(bars):
    dates = [b["date"] for b in bars]
    opens = [b["open"] for b in bars]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    vols = [b["volume"] for b in bars]

    candles = [
        {"time": d, "open": o, "high": h, "low": lo, "close": c}
        for d, o, h, lo, c in zip(dates, opens, highs, lows, closes)
    ]
    volume = [{"time": d, "value": float(v)} for d, v in zip(dates, vols)]

    up, mid, lo_band = bollinger(closes)
    macd_line, signal_line, hist = macd(closes)
    k_series, d_series = stochastic(highs, lows, closes)
    atr_series = atr(highs, lows, closes)

    price = round(float(closes[-1]), 2)
    sr = support_resistance(highs, lows, price)

    return {
        "candles": candles,
        "volume": volume,
        "bollinger": {
            "upper": _line(dates, up),
            "middle": _line(dates, mid),
            "lower": _line(dates, lo_band),
        },
        "rsi": _line(dates, rsi(closes)),
        "macd": {
            "macd": _line(dates, macd_line),
            "signal": _line(dates, signal_line),
            "hist": _line(dates, hist),
        },
        "stochastic": {"k": _line(dates, k_series), "d": _line(dates, d_series)},
        "atr": _line(dates, atr_series),
        "support": sr["support"],
        "resistance": sr["resistance"],
    }


RESOLUTIONS = [("1h", "3mo"), ("1d", "5y"), ("1wk", "max"), ("1mo", "max")]


def build_chart_payload(ticker, market=None, period=None):
    resolutions = {}
    for res, default_period in RESOLUTIONS:
        p = period if (res == "1d" and period) else default_period
        raw = history(ticker, p, market, interval=res)
        if "error" in raw:
            continue
        bars = [b for b in raw.get("bars") or []
                if all(isinstance(b.get(k), (int, float)) and math.isfinite(b[k])
                       for k in ("open", "high", "low", "close"))]
        if len(bars) < 30:
            continue
        resolutions[res] = {"_bars_last_close": round(float(bars[-1]["close"]), 2),
                            "_bars_last_date": bars[-1]["date"],
                            **series_from_bars(bars)}
    if not resolutions:
        return {"error": f"chart: no resolutions available for {ticker}"}
    default = "1d" if "1d" in resolutions else next(iter(resolutions))
    sym = normalize_ticker(ticker, market)  # label only — no extra fetch
    as_of = resolutions[default].pop("_bars_last_date")
    price = resolutions[default].pop("_bars_last_close")
    for r in resolutions.values():
        r.pop("_bars_last_close", None)
        r.pop("_bars_last_date", None)
    try:
        f = fundamentals_analyze(ticker, market)
    except Exception:  # noqa: BLE001 — fundamentals are optional, never fatal
        f = None
    fundamentals = None if (not f or "error" in f) else f
    return {"ticker": sym, "as_of": as_of, "price": price,
            "default": default, "resolutions": resolutions, "fundamentals": fundamentals}


def build_chart_data(ticker, market=None, period="1y"):
    raw = history(ticker, period, market)
    if "error" in raw:
        return raw
    bars = raw.get("bars") or []
    bars = [b for b in bars
            if all(isinstance(b.get(k), (int, float)) and math.isfinite(b[k])
                   for k in ("open", "high", "low", "close"))]
    if len(bars) < 30:
        return {"error": f"chart: not enough history for {raw.get('ticker', ticker)} ({period})"}
    series = series_from_bars(bars)
    return {
        "ticker": raw.get("ticker", ticker),
        "period": period,
        "as_of": bars[-1]["date"],
        "price": round(float(bars[-1]["close"]), 2),
        **series,
    }
