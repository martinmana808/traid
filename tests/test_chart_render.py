import json
from tools.chart_render import render_chart_html, render_session_index


def _payload():
    series = {
        "candles": [{"time": "2026-06-26", "open": 1, "high": 2, "low": 0.5, "close": 198.18}],
        "volume": [{"time": "2026-06-26", "value": 1000.0}],
        "bollinger": {"upper": [{"time": "2026-06-26"}], "middle": [{"time": "2026-06-26"}],
                      "lower": [{"time": "2026-06-26"}]},
        "rsi": [{"time": "2026-06-26", "value": 44.0}],
        "macd": {"macd": [{"time": "2026-06-26", "value": 0.1}],
                 "signal": [{"time": "2026-06-26", "value": 0.2}],
                 "hist": [{"time": "2026-06-26", "value": -0.1}]},
        "stochastic": {"k": [{"time": "2026-06-26", "value": 50.0}],
                       "d": [{"time": "2026-06-26", "value": 55.0}]},
        "support": 190.0, "resistance": 205.0,
    }
    return {"ticker": "NVDA", "as_of": "2026-06-26", "price": 198.18,
            "default": "1d", "resolutions": {"1d": series, "1wk": series, "1mo": series}}


def test_render_embeds_payload_and_controls():
    html = render_chart_html(_payload())
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert "lightweight-charts@4.1.3" in html
    assert "__DATA__" not in html
    for cid in ("price", "rsi", "macd", "stoch"):
        assert f'id="{cid}"' in html
    assert 'id="timeframe"' in html
    # a button per present resolution (1d/1wk/1mo here; no 1h)
    assert 'data-res="1d"' in html and 'data-res="1wk"' in html and 'data-res="1mo"' in html
    assert 'data-res="1h"' not in html
    assert "minimumWidth" in html
    assert "subscribeVisibleLogicalRangeChange" in html
    assert "loadResolution" in html


def test_render_payload_json_roundtrips():
    import json
    html = render_chart_html(_payload())
    start = html.index("const DATA = ") + len("const DATA = ")
    end = html.index(";\n", start)
    parsed = json.loads(html[start:end])
    assert parsed["default"] == "1d"
    assert parsed["resolutions"]["1d"]["support"] == 190.0


def test_render_embeds_call_metadata():
    html = render_chart_html(_payload(), {"call": "buy", "confidence": "high", "call_date": "2026-06-28"})
    assert "buy" in html and "high" in html


def test_render_has_panel_and_crosshair_link():
    html = render_chart_html(_payload())
    assert 'id="panel"' in html
    assert "subscribeCrosshairMove" in html
    assert "setCrosshairPosition" in html
    # summary recompute is wired to range changes too
    assert html.count("subscribeVisibleLogicalRangeChange") >= 1


def test_session_index_links_each_entry():
    html = render_session_index("2026-06-28", [
        {"ticker": "META", "call": "buy", "filename": "META-2026-06-28-001.html"},
        {"ticker": "VT", "call": None, "filename": "VT-2026-06-28-002.html"},
    ])
    assert "2026-06-28" in html
    assert 'href="META-2026-06-28-001.html"' in html
    assert 'href="VT-2026-06-28-002.html"' in html
    assert "META" in html and "VT" in html
    assert "buy" in html
