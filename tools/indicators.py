"""Technical indicator engine for TRaid.

Computes a full suite of indicators from OHLCV and returns both the numeric
values and plain-English readings, plus a confluence tally. RSI and ATR use
Wilder's smoothing (RMA) to match TradingView.

Usage (CLI):
    python tools/indicators.py NVDA
    python tools/indicators.py AIR --market NZX
    python tools/indicators.py VOO --period 2y

Indicators are CONTEXT for timing, not blind buy/sell triggers.
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

# Make `tools.*` importable whether run as a script (python tools/indicators.py)
# or as a module (pytest). Without this, direct CLI execution can't find the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.market import normalize_ticker, error_response


# --- Wilder's smoothing (RMA) ---------------------------------------------
def _rma(series, period):
    return series.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def _ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


# --- Pure indicator functions ---------------------------------------------
def sma(closes, period):
    return pd.Series(closes, dtype="float64").rolling(period).mean()


def rsi(closes, period=14):
    closes = pd.Series(closes, dtype="float64")
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = _rma(gain, period)
    avg_loss = _rma(loss, period)
    rs = avg_gain / avg_loss
    out = 100.0 - 100.0 / (1.0 + rs)
    # avg_loss == 0 with gains -> 100 ; fully flat (both 0) -> 50 (neutral)
    out = out.mask(avg_loss == 0, 100.0)
    out = out.mask((avg_gain == 0) & (avg_loss == 0), 50.0)
    return out


def macd(closes, fast=12, slow=26, signal=9):
    closes = pd.Series(closes, dtype="float64")
    macd_line = _ema(closes, fast) - _ema(closes, slow)
    signal_line = _ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def bollinger(closes, period=20, num_std=2):
    closes = pd.Series(closes, dtype="float64")
    mid = closes.rolling(period).mean()
    sd = closes.rolling(period).std(ddof=0)
    upper = mid + num_std * sd
    lower = mid - num_std * sd
    return upper, mid, lower


def atr(highs, lows, closes, period=14):
    h = pd.Series(highs, dtype="float64")
    low_ = pd.Series(lows, dtype="float64")
    c = pd.Series(closes, dtype="float64")
    prev_close = c.shift(1)
    tr = pd.concat(
        [(h - low_), (h - prev_close).abs(), (low_ - prev_close).abs()], axis=1
    ).max(axis=1)
    return _rma(tr, period)


def stochastic(highs, lows, closes, k=14, d=3):
    h = pd.Series(highs, dtype="float64")
    low_ = pd.Series(lows, dtype="float64")
    c = pd.Series(closes, dtype="float64")
    ll = low_.rolling(k).min()
    hh = h.rolling(k).max()
    percent_k = 100.0 * (c - ll) / (hh - ll)
    percent_d = percent_k.rolling(d).mean()
    return percent_k, percent_d


def volume_trend(volumes, period=20):
    v = pd.Series(volumes, dtype="float64")
    avg = v.rolling(period).mean()
    return v / avg


def confluence(signals):
    bullish = signals.count("bullish")
    bearish = signals.count("bearish")
    neutral = signals.count("neutral")
    net = bullish - bearish
    if net >= 2:
        summary = "net bullish confluence"
    elif net <= -2:
        summary = "net bearish confluence"
    else:
        summary = "mixed / no strong edge"
    return {
        "bullish": bullish,
        "bearish": bearish,
        "neutral": neutral,
        "summary": summary,
        "note": "Context only — NOT a trade trigger. Indicators describe momentum/trend/volatility; they do not predict.",
    }


# --- Readings (value -> plain English + signal tag) -----------------------
def _round(x, n=2):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


def analyze(ticker, market=None, period="1y"):
    sym = normalize_ticker(ticker, market)
    try:
        import yfinance as yf
        df = yf.Ticker(sym).history(period=period)
    except Exception as e:  # noqa: BLE001
        return error_response(f"indicators: history fetch failed for {sym}: {e}")
    if df is None or df.empty or len(df) < 30:
        return error_response(f"indicators: not enough history for {sym} ({period})")

    closes = df["Close"].tolist()
    highs = df["High"].tolist()
    lows = df["Low"].tolist()
    vols = df["Volume"].tolist()
    price = round(float(closes[-1]), 2)
    as_of = df.index[-1].date().isoformat()

    rsi_v = _round(rsi(closes).dropna().iloc[-1])
    macd_line, signal_line, hist = macd(closes)
    macd_v, sig_v, hist_v = _round(macd_line.iloc[-1], 4), _round(signal_line.iloc[-1], 4), _round(hist.iloc[-1], 4)
    # crossover within last 3 bars?
    recent_hist = hist.dropna().tail(4).tolist()
    crossed = any((recent_hist[i] <= 0 < recent_hist[i + 1]) or (recent_hist[i] >= 0 > recent_hist[i + 1])
                  for i in range(len(recent_hist) - 1)) if len(recent_hist) > 1 else False
    up, mid, lo = bollinger(closes)
    up_v, mid_v, lo_v = _round(up.iloc[-1]), _round(mid.iloc[-1]), _round(lo.iloc[-1])
    pct_b = _round((price - lo_v) / (up_v - lo_v), 2) if up_v and lo_v and up_v != lo_v else None
    sma50 = _round(sma(closes, 50).iloc[-1]) if len(closes) >= 50 else None
    sma200 = _round(sma(closes, 200).iloc[-1]) if len(closes) >= 200 else None
    atr_v = _round(atr(highs, lows, closes).iloc[-1])
    atr_pct = _round(atr_v / price * 100, 2) if atr_v else None
    k_series, d_series = stochastic(highs, lows, closes)
    k_v, d_v = _round(k_series.iloc[-1]), _round(d_series.iloc[-1])
    vol_ratio = _round(volume_trend(vols).iloc[-1], 2)

    signals = []

    # RSI
    if rsi_v is None:
        rsi_sig, rsi_read = "neutral", "RSI unavailable"
    elif rsi_v >= 70:
        rsi_sig, rsi_read = "bearish", f"RSI {rsi_v} — overbought (stretched, pullback risk)"
    elif rsi_v <= 30:
        rsi_sig, rsi_read = "bullish", f"RSI {rsi_v} — oversold (potential bounce)"
    else:
        rsi_sig, rsi_read = "neutral", f"RSI {rsi_v} — neutral"
    signals.append(rsi_sig)

    # MACD
    macd_sig = "bullish" if (macd_v is not None and macd_v > sig_v) else "bearish"
    macd_read = (
        f"MACD {'above' if macd_sig == 'bullish' else 'below'} signal "
        f"({macd_v} vs {sig_v}), histogram {hist_v}"
        + (" — fresh crossover (last ~3 bars)" if crossed else "")
    )
    signals.append(macd_sig)

    # Bollinger
    if pct_b is None:
        boll_sig, boll_read = "neutral", "Bollinger unavailable"
    elif pct_b > 1:
        boll_sig, boll_read = "bearish", f"price above upper band (%B {pct_b}) — stretched high"
    elif pct_b < 0:
        boll_sig, boll_read = "bullish", f"price below lower band (%B {pct_b}) — stretched low"
    else:
        boll_sig, boll_read = "neutral", f"price within bands (%B {pct_b}), mid {mid_v}"
    signals.append(boll_sig)

    # Trend (SMA 50/200)
    if sma50 and sma200:
        above_both = price > sma50 and price > sma200
        cross = "golden cross (50>200)" if sma50 > sma200 else "death cross (50<200)"
        if above_both and sma50 > sma200:
            trend_sig = "bullish"
        elif price < sma50 and price < sma200 and sma50 < sma200:
            trend_sig = "bearish"
        else:
            trend_sig = "neutral"
        trend_read = f"price {price} vs 50d {sma50} / 200d {sma200} — {cross}"
    elif sma50:
        trend_sig = "bullish" if price > sma50 else "bearish"
        trend_read = f"price {price} vs 50d {sma50} (200d needs more history)"
    else:
        trend_sig, trend_read = "neutral", "trend unavailable (insufficient history)"
    signals.append(trend_sig)

    # Stochastic
    if k_v is None:
        stoch_sig, stoch_read = "neutral", "stochastic unavailable"
    elif k_v >= 80:
        stoch_sig, stoch_read = "bearish", f"stochastic %K {k_v} — overbought"
    elif k_v <= 20:
        stoch_sig, stoch_read = "bullish", f"stochastic %K {k_v} — oversold"
    else:
        stoch_sig, stoch_read = "neutral", f"stochastic %K {k_v} / %D {d_v} — neutral"
    signals.append(stoch_sig)

    # Volume + ATR are context, not bull/bear votes
    vol_read = (
        f"volume {vol_ratio}x its 20-day average"
        + (" — elevated" if vol_ratio and vol_ratio >= 1.5 else (" — quiet" if vol_ratio and vol_ratio <= 0.5 else ""))
    )
    atr_read = f"ATR {atr_v} (~{atr_pct}% of price) — typical daily range / volatility"

    return {
        "ticker": sym,
        "period": period,
        "as_of": as_of,
        "price": _round(price),
        "indicators": {
            "rsi": {"value": rsi_v, "signal": rsi_sig, "reading": rsi_read},
            "macd": {"macd": macd_v, "signal": sig_v, "histogram": hist_v,
                     "crossover_recent": crossed, "signal_tag": macd_sig, "reading": macd_read},
            "bollinger": {"upper": up_v, "middle": mid_v, "lower": lo_v, "percent_b": pct_b,
                          "signal": boll_sig, "reading": boll_read},
            "trend": {"sma50": sma50, "sma200": sma200, "signal": trend_sig, "reading": trend_read},
            "stochastic": {"k": k_v, "d": d_v, "signal": stoch_sig, "reading": stoch_read},
            "atr": {"value": atr_v, "pct_of_price": atr_pct, "reading": atr_read},
            "volume": {"ratio_to_20d_avg": vol_ratio, "reading": vol_read},
        },
        "confluence": confluence(signals),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="TRaid technical indicators")
    p.add_argument("ticker")
    p.add_argument("--market", default=None)
    p.add_argument("--period", default="1y")
    args = p.parse_args(argv)
    print(json.dumps(analyze(args.ticker, args.market, args.period), indent=2))


if __name__ == "__main__":
    main()
