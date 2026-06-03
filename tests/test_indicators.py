import pandas as pd
from tools.indicators import (
    rsi, macd, bollinger, sma, atr, stochastic, volume_trend, confluence,
)


def last(series):
    return float(series.dropna().iloc[-1])


def test_sma_exact():
    assert last(sma([1, 2, 3, 4, 5], 5)) == 3.0


def test_rsi_monotonic_up_is_100():
    assert last(rsi(list(range(1, 40)), 14)) == 100.0


def test_rsi_monotonic_down_is_0():
    assert last(rsi(list(range(40, 1, -1)), 14)) == 0.0


def test_rsi_flat_is_50():
    assert last(rsi([10.0] * 40, 14)) == 50.0


def test_macd_constant_series_is_zero():
    macd_line, signal_line, hist = macd([5.0] * 60)
    assert abs(last(macd_line)) < 1e-9
    assert abs(last(hist)) < 1e-9


def test_bollinger_middle_equals_sma():
    closes = [float(x) for x in range(1, 41)]
    upper, mid, lower = bollinger(closes, 20, 2)
    assert last(mid) == last(sma(closes, 20))
    assert last(upper) > last(mid) > last(lower)


def test_stochastic_close_at_high_is_100():
    highs = [10.0] * 20
    lows = [5.0] * 20
    closes = [6.0] * 19 + [10.0]  # last close == period high
    k, d = stochastic(highs, lows, closes, 14, 3)
    assert last(k) == 100.0


def test_stochastic_close_at_low_is_0():
    highs = [10.0] * 20
    lows = [5.0] * 20
    closes = [6.0] * 19 + [5.0]  # last close == period low
    k, d = stochastic(highs, lows, closes, 14, 3)
    assert last(k) == 0.0


def test_atr_constant_range():
    # high-low always 2, no gaps -> ATR converges to 2
    highs = [12.0] * 30
    lows = [10.0] * 30
    closes = [11.0] * 30
    assert abs(last(atr(highs, lows, closes, 14)) - 2.0) < 1e-6


def test_volume_trend_constant_is_one():
    assert abs(last(volume_trend([1000.0] * 30, 20)) - 1.0) < 1e-9


def test_confluence_tally():
    signals = ["bullish", "bullish", "bearish", "neutral"]
    out = confluence(signals)
    assert out["bullish"] == 2 and out["bearish"] == 1 and out["neutral"] == 1
    assert "not a trade" in out["note"].lower()
