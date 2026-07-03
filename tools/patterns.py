"""Candlestick pattern detection for TRaid (Phase 4 — the 'Vision').

Detects classic candlestick patterns from OHLC with a 0-100 match score, plus
basic price structure (swing pivots, support/resistance, swing-trend).

HONESTY: candlestick/chart patterns have weak, contested predictive power. This
is presented as 'what a chart-reader would note' — low-weight CONTEXT, never a
predictor. Named multi-candle chart formations (head & shoulders, flags) are
deliberately NOT faked here.

Usage:
    python tools/patterns.py NVDA
    python tools/patterns.py AIR --market NZX --period 6mo
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.market import normalize_ticker, error_response  # noqa: E402


# --- candle geometry helpers ----------------------------------------------
def _body(b):
    return abs(b["close"] - b["open"])


def _range(b):
    return b["high"] - b["low"]


def _upper(b):
    return b["high"] - max(b["open"], b["close"])


def _lower(b):
    return min(b["open"], b["close"]) - b["low"]


# --- single-candle patterns -----------------------------------------------
def doji(bars):
    b = bars[-1]
    rng = _range(b)
    if rng == 0:
        return 0
    ratio = _body(b) / rng
    return round((1 - ratio / 0.1) * 100) if ratio < 0.1 else 0


def hammer(bars):
    """Long lower shadow, small body up top, tiny upper shadow (bullish reversal)."""
    b = bars[-1]
    rng = _range(b)
    if rng == 0:
        return 0
    body, lower, upper = _body(b), _lower(b), _upper(b)
    if lower >= 0.6 * rng and upper <= 0.1 * rng and body <= 0.3 * rng:
        return round(min(100, 50 + (lower / rng - 0.6) / 0.4 * 50))
    return 0


def shooting_star(bars):
    """Long upper shadow, small body down low, tiny lower shadow (bearish reversal)."""
    b = bars[-1]
    rng = _range(b)
    if rng == 0:
        return 0
    body, lower, upper = _body(b), _lower(b), _upper(b)
    if upper >= 0.6 * rng and lower <= 0.1 * rng and body <= 0.3 * rng:
        return round(min(100, 50 + (upper / rng - 0.6) / 0.4 * 50))
    return 0


def inverted_hammer(bars):
    """Same shape as a shooting star (long upper shadow); bullish when it appears
    after a downtrend. analyze() picks the right label using trend context."""
    return shooting_star(bars)


# --- two-candle patterns ---------------------------------------------------
def bullish_engulfing(bars):
    if len(bars) < 2:
        return 0
    prev, cur = bars[-2], bars[-1]
    if (prev["close"] < prev["open"] and cur["close"] > cur["open"]
            and cur["open"] <= prev["close"] and cur["close"] >= prev["open"]):
        pb, cb = _body(prev), _body(cur)
        return 70 if pb == 0 else round(min(100, 50 + min(1, cb / pb - 1) * 50))
    return 0


def bearish_engulfing(bars):
    if len(bars) < 2:
        return 0
    prev, cur = bars[-2], bars[-1]
    if (prev["close"] > prev["open"] and cur["close"] < cur["open"]
            and cur["open"] >= prev["close"] and cur["close"] <= prev["open"]):
        pb, cb = _body(prev), _body(cur)
        return 70 if pb == 0 else round(min(100, 50 + min(1, cb / pb - 1) * 50))
    return 0


# --- three-candle patterns -------------------------------------------------
def morning_star(bars):
    if len(bars) < 3:
        return 0
    c1, c2, c3 = bars[-3], bars[-2], bars[-1]
    c1b = _body(c1)
    if not (c1["close"] < c1["open"] and c3["close"] > c3["open"]) or c1b == 0:
        return 0
    c1_mid = (c1["open"] + c1["close"]) / 2
    if _body(c2) <= 0.5 * c1b and c3["close"] > c1_mid and _body(c3) >= 0.5 * c1b:
        denom = c1["open"] - c1_mid
        return 75 if denom == 0 else round(min(100, 50 + (c3["close"] - c1_mid) / denom * 50))
    return 0


def evening_star(bars):
    if len(bars) < 3:
        return 0
    c1, c2, c3 = bars[-3], bars[-2], bars[-1]
    c1b = _body(c1)
    if not (c1["close"] > c1["open"] and c3["close"] < c3["open"]) or c1b == 0:
        return 0
    c1_mid = (c1["open"] + c1["close"]) / 2
    if _body(c2) <= 0.5 * c1b and c3["close"] < c1_mid and _body(c3) >= 0.5 * c1b:
        denom = c1_mid - c1["open"]
        return 75 if denom == 0 else round(min(100, 50 + (c1_mid - c3["close"]) / denom * 50))
    return 0


# --- structure -------------------------------------------------------------
def find_pivots(highs, lows, window=2):
    piv = []
    n = len(highs)
    for i in range(window, n - window):
        seg_h = highs[i - window:i + window + 1]
        if highs[i] == max(seg_h) and highs[i] > min(seg_h):
            piv.append({"index": i, "kind": "high", "price": highs[i]})
        seg_l = lows[i - window:i + window + 1]
        if lows[i] == min(seg_l) and lows[i] < max(seg_l):
            piv.append({"index": i, "kind": "low", "price": lows[i]})
    return piv


def support_resistance(highs, lows, price, window=3):
    """Nearest pivot-based support/resistance around `price`.

    Restored for the interactive chart (tools/chart_data). Mirrors the inline
    structure logic in analyze(): nearest swing-high above price = resistance,
    nearest swing-low below price = support; fall back to period extremes.
    """
    piv = find_pivots(highs, lows, window=window)
    high_piv = [p["price"] for p in piv if p["kind"] == "high"]
    low_piv = [p["price"] for p in piv if p["kind"] == "low"]
    resistance = min([h for h in high_piv if h > price], default=round(max(highs), 2))
    support = max([lo for lo in low_piv if lo < price], default=round(min(lows), 2))
    return {"support": round(support, 2), "resistance": round(resistance, 2)}


_MEANING = {
    "doji": "indecision / potential turning point",
    "hammer": "bullish reversal (buyers rejected lower prices)",
    "inverted_hammer": "bullish reversal signal (after a downtrend)",
    "shooting_star": "bearish reversal (sellers rejected higher prices)",
    "bullish_engulfing": "bullish reversal (buyers overwhelmed sellers)",
    "bearish_engulfing": "bearish reversal (sellers overwhelmed buyers)",
    "morning_star": "bullish reversal (3-candle bottoming)",
    "evening_star": "bearish reversal (3-candle topping)",
}


def analyze(ticker, market=None, period="3mo"):
    sym = normalize_ticker(ticker, market)
    try:
        import yfinance as yf
        df = yf.Ticker(sym).history(period=period)
    except Exception as e:  # noqa: BLE001
        return error_response(f"patterns: history fetch failed for {sym}: {e}")
    if df is None or df.empty or len(df) < 10:
        return error_response(f"patterns: not enough history for {sym} ({period})")

    bars = [
        {"open": float(r["Open"]), "high": float(r["High"]),
         "low": float(r["Low"]), "close": float(r["Close"])}
        for _, r in df.iterrows()
    ]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    price = round(bars[-1]["close"], 2)
    short_trend = "up" if len(bars) >= 6 and bars[-1]["close"] > bars[-6]["close"] else "down"

    # single-candle: resolve the long-upper-shadow shape by trend context
    star_name = "shooting_star" if short_trend == "up" else "inverted_hammer"
    candidates = [
        ("doji", doji(bars)),
        ("hammer", hammer(bars)),
        (star_name, shooting_star(bars)),
        ("bullish_engulfing", bullish_engulfing(bars)),
        ("bearish_engulfing", bearish_engulfing(bars)),
        ("morning_star", morning_star(bars)),
        ("evening_star", evening_star(bars)),
    ]
    detected = [
        {"pattern": name, "match_score": score, "meaning": _MEANING[name]}
        for name, score in candidates if score >= 50
    ]

    # structure
    piv = find_pivots(highs, lows, window=3)
    high_piv = [p["price"] for p in piv if p["kind"] == "high"]
    low_piv = [p["price"] for p in piv if p["kind"] == "low"]
    resistance = min([h for h in high_piv if h > price], default=round(max(highs), 2))
    support = max([lo for lo in low_piv if lo < price], default=round(min(lows), 2))
    if len(high_piv) >= 2 and len(low_piv) >= 2:
        swing = ("rising" if high_piv[-1] > high_piv[-2] and low_piv[-1] > low_piv[-2]
                 else "falling" if high_piv[-1] < high_piv[-2] and low_piv[-1] < low_piv[-2]
                 else "sideways")
    else:
        swing = "unclear (too few swings)"

    return {
        "ticker": sym,
        "period": period,
        "as_of": df.index[-1].date().isoformat(),
        "price": price,
        "patterns": detected,
        "structure": {
            "swing_trend": swing,
            "nearest_support": round(support, 2),
            "nearest_resistance": round(resistance, 2),
        },
        "note": (
            "Candlestick patterns are LOW-WEIGHT CONTEXT — their predictive power is "
            "weak and contested. Use as confluence with trend/fundamentals/risk, never alone."
        ),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="TRaid candlestick pattern detection")
    p.add_argument("ticker")
    p.add_argument("--market", default=None)
    p.add_argument("--period", default="3mo")
    args = p.parse_args(argv)
    print(json.dumps(analyze(args.ticker, args.market, args.period), indent=2))


if __name__ == "__main__":
    main()
