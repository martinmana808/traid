import json
from tools.chart_render import render_chart_html


def _data():
    return {
        "ticker": "NVDA", "period": "1y", "as_of": "2026-06-26", "price": 198.18,
        "candles": [{"time": "2026-06-26", "open": 1, "high": 2, "low": 0.5, "close": 198.18}],
        "volume": [{"time": "2026-06-26", "value": 1000.0}],
        "bollinger": {"upper": [], "middle": [], "lower": []},
        "rsi": [{"time": "2026-06-26", "value": 44.0}],
        "macd": {"macd": [], "signal": [], "hist": []},
        "stochastic": {"k": [], "d": []},
        "support": 190.0, "resistance": 205.0,
    }


def test_render_is_self_contained_html():
    html = render_chart_html(_data())
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert "lightweight-charts@4.1.3" in html
    assert "__DATA__" not in html  # token fully substituted
    # embedded data is present and parseable-looking
    assert "198.18" in html
    assert "NVDA" in html
    for cid in ("price", "rsi", "macd", "stoch"):
        assert f'id="{cid}"' in html


def test_render_embeds_call_metadata():
    html = render_chart_html(_data(), {"call": "buy", "confidence": "high", "call_date": "2026-06-28"})
    assert "buy" in html
    assert "high" in html


def test_embedded_json_roundtrips():
    html = render_chart_html(_data())
    start = html.index("const DATA = ") + len("const DATA = ")
    end = html.index(";\n", start)
    parsed = json.loads(html[start:end])
    assert parsed["ticker"] == "NVDA"
    assert parsed["support"] == 190.0
