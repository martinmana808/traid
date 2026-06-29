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

from tools.indicators import rsi, macd, bollinger, stochastic  # noqa: E402
from tools.patterns import support_resistance  # noqa: E402
from tools.market import history  # noqa: E402


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
        "support": sr["support"],
        "resistance": sr["resistance"],
    }


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
