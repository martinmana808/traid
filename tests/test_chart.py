import os
from tools.chart import write_chart


def _data():
    return {
        "ticker": "NVDA", "period": "1y", "as_of": "2026-06-26", "price": 198.18,
        "candles": [{"time": "2026-06-26", "open": 1, "high": 2, "low": 0.5, "close": 198.18}],
        "volume": [{"time": "2026-06-26", "value": 1000.0}],
        "bollinger": {"upper": [], "middle": [], "lower": []},
        "rsi": [], "macd": {"macd": [], "signal": [], "hist": []},
        "stochastic": {"k": [], "d": []}, "support": 190.0, "resistance": 205.0,
    }


def test_write_chart_creates_self_contained_file(tmp_path):
    out = write_chart(_data(), {}, str(tmp_path / "live"), "NVDA-2026-06-26.html")
    assert os.path.exists(out)
    html = open(out, encoding="utf-8").read()
    assert "lightweight-charts@4.1.3" in html
    assert "198.18" in html
    assert "NVDA" in html


def test_write_chart_returns_path_under_out_dir(tmp_path):
    out = write_chart(_data(), {}, str(tmp_path / "sub"), "x.html")
    assert out.endswith(os.path.join("sub", "x.html"))


import tools.chart as chart


def test_generate_chart_snapshot_embeds_call_label(tmp_path, monkeypatch):
    data = _data()
    monkeypatch.setattr(chart, "build_chart_data", lambda t, m=None, p="1y": dict(data))
    out = chart.generate_chart("NVDA", charts_root=str(tmp_path), snapshot=True,
                               call_id="2026-06-28-001",
                               call_meta={"call": "buy", "confidence": "high",
                                          "call_date": "2026-06-28"},
                               open_browser=False)
    html = open(out, encoding="utf-8").read()
    assert "buy" in html and "high" in html and "2026-06-28" in html
