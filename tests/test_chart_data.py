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


def test_indicator_series_are_full_length_with_whitespace_warmup():
    out = series_from_bars(_bars(60))
    assert len(out["candles"]) == 60
    # every indicator series now has one point per bar (whitespace during warm-up)
    assert len(out["rsi"]) == 60
    assert len(out["bollinger"]["upper"]) == 60
    assert len(out["macd"]["macd"]) == 60
    assert len(out["stochastic"]["k"]) == 60
    # warm-up points are whitespace: time only, no value
    assert out["rsi"][0] == {"time": out["candles"][0]["time"]}
    # later points carry a numeric value
    valued = [p for p in out["rsi"] if "value" in p]
    assert 0 < len(valued) < 60
    for p in valued:
        assert not math.isnan(p["value"])
    # every point has a time, in the same order as candles
    assert [p["time"] for p in out["rsi"]] == [c["time"] for c in out["candles"]]


def test_support_resistance_present():
    out = series_from_bars(_bars(60))
    assert isinstance(out["support"], float)
    assert isinstance(out["resistance"], float)
    assert out["support"] <= out["resistance"]


import tools.chart_data as cd


def test_build_chart_data_uses_market_history(monkeypatch):
    fake = {"ticker": "TEST", "period": "1y",
            "bars": _bars(60)}
    monkeypatch.setattr(cd, "history", lambda t, p, m=None: fake)
    out = cd.build_chart_data("test", period="1y")
    assert out["ticker"] == "TEST"
    assert out["as_of"] == fake["bars"][-1]["date"]
    assert out["price"] == round(fake["bars"][-1]["close"], 2)
    assert "candles" in out and len(out["candles"]) == 60


def test_build_chart_data_propagates_error(monkeypatch):
    monkeypatch.setattr(cd, "history", lambda t, p, m=None: {"error": "boom"})
    out = cd.build_chart_data("nope")
    assert out["error"] == "boom"


def test_build_chart_data_rejects_short_history(monkeypatch):
    monkeypatch.setattr(cd, "history",
                        lambda t, p, m=None: {"ticker": "X", "period": p, "bars": _bars(10)})
    out = cd.build_chart_data("x")
    assert "error" in out


def test_build_chart_data_drops_nan_bars(monkeypatch):
    bars = _bars(60)
    bars[5]["close"] = float("nan")
    bars[6]["open"] = float("nan")
    monkeypatch.setattr(cd, "history", lambda t, p, m=None: {"ticker": "X", "period": p, "bars": bars})
    out = cd.build_chart_data("x")
    assert "error" not in out
    assert len(out["candles"]) == 58  # two NaN bars dropped


def test_build_chart_payload_shape(monkeypatch):
    def fake_history(t, p, m=None, interval="1d"):
        return {"ticker": "NVDA", "period": p, "bars": _bars(60)}
    monkeypatch.setattr(cd, "history", fake_history)
    pay = cd.build_chart_payload("nvda")
    assert pay["ticker"] == "NVDA"
    assert pay["default"] == "1d"
    assert set(pay["resolutions"]) == {"1h", "1d", "1wk", "1mo"}
    assert "candles" in pay["resolutions"]["1d"]
    assert pay["price"] == round(_bars(60)[-1]["close"], 2)


def test_build_chart_payload_omits_failed_resolution(monkeypatch):
    def fake_history(t, p, m=None, interval="1d"):
        if interval == "1h":
            return {"error": "no intraday"}
        return {"ticker": "NVDA", "period": p, "bars": _bars(60)}
    monkeypatch.setattr(cd, "history", fake_history)
    pay = cd.build_chart_payload("nvda")
    assert "1h" not in pay["resolutions"]
    assert pay["default"] == "1d"


def test_build_chart_payload_default_falls_back(monkeypatch):
    def fake_history(t, p, m=None, interval="1d"):
        if interval == "1d":
            return {"error": "boom"}
        return {"ticker": "NVDA", "period": p, "bars": _bars(60)}
    monkeypatch.setattr(cd, "history", fake_history)
    pay = cd.build_chart_payload("nvda")
    assert pay["default"] in pay["resolutions"]
    assert pay["default"] != "1d"


def test_series_includes_atr_full_length():
    out = series_from_bars(_bars(60))
    assert "atr" in out
    assert len(out["atr"]) == 60
    assert [p["time"] for p in out["atr"]] == [c["time"] for c in out["candles"]]
    assert any("value" in p for p in out["atr"])


def test_payload_embeds_fundamentals(monkeypatch):
    def fake_history(t, p, m=None, interval="1d"):
        return {"ticker": "NVDA", "period": p, "bars": _bars(60)}
    monkeypatch.setattr(cd, "history", fake_history)
    monkeypatch.setattr(cd, "fundamentals_analyze",
                        lambda t, m=None: {"name": "NVIDIA", "valuation": {"peg": 0.7}})
    pay = cd.build_chart_payload("nvda")
    assert pay["fundamentals"]["valuation"]["peg"] == 0.7


def test_payload_fundamentals_none_on_error(monkeypatch):
    def fake_history(t, p, m=None, interval="1d"):
        return {"ticker": "NVDA", "period": p, "bars": _bars(60)}
    monkeypatch.setattr(cd, "history", fake_history)
    monkeypatch.setattr(cd, "fundamentals_analyze", lambda t, m=None: {"error": "no data"})
    pay = cd.build_chart_payload("nvda")
    assert pay["fundamentals"] is None
