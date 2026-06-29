import math
from tools.chart_data import series_from_bars


def _bars(n=60):
    # deterministic gently-rising sawtooth so indicators are well-defined
    bars = []
    for i in range(n):
        base = 100 + i * 0.5 + (2 if i % 3 == 0 else 0)
        bars.append({
            "date": f"2026-01-{(i % 28) + 1:02d}",  # not necessarily unique; fine for math
            "open": base - 1, "high": base + 2, "low": base - 2,
            "close": base, "volume": 1000 + i,
        })
    # force unique ascending dates for series alignment
    for i, b in enumerate(bars):
        b["date"] = f"2026-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}"
    return bars


def test_series_shapes_and_no_nan():
    out = series_from_bars(_bars(60))
    assert len(out["candles"]) == 60
    assert set(out["candles"][0]) == {"time", "open", "high", "low", "close"}
    # indicator series drop warm-up NaNs, so they are shorter than candles
    assert 0 < len(out["rsi"]) < 60
    for pt in out["rsi"]:
        assert set(pt) == {"time", "value"}
        assert not math.isnan(pt["value"])
    assert {"upper", "middle", "lower"} == set(out["bollinger"])
    assert {"macd", "signal", "hist"} == set(out["macd"])
    assert {"k", "d"} == set(out["stochastic"])


def test_support_resistance_present():
    out = series_from_bars(_bars(60))
    assert isinstance(out["support"], float)
    assert isinstance(out["resistance"], float)
    assert out["support"] <= out["resistance"]
