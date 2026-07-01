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
        "atr": [{"time": "2026-06-26", "value": 5.2}],
        "sma50": [{"time": "2026-06-26", "value": 185.0}],
        "sma200": [{"time": "2026-06-26", "value": 175.0}],
        "support": 190.0, "resistance": 205.0,
    }
    return {"ticker": "NVDA", "as_of": "2026-06-26", "price": 198.18,
            "default": "1d", "resolutions": {"1d": series, "1wk": series, "1mo": series},
            "fundamentals": None}


def test_render_panel_has_richer_stats_and_fundamentals():
    pay = _payload()
    pay["fundamentals"] = {"name": "NVIDIA", "sector": "Tech",
                           "valuation": {"trailing_pe": 50, "forward_pe": 30, "peg": 0.7,
                                         "reading": "P/E 50 — high"},
                           "growth": {"revenue_growth_pct": 60, "reading": "60% — strong"},
                           "profitability": {"profit_margin_pct": 55, "reading": "55% — high"}}
    html = render_chart_html(pay)
    assert "Fundamentals" in html
    assert "PEG" in html
    # ATR / %B / distance-to-S/R stat labels present in the panel JS
    assert "ATR" in html and "%B" in html


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


def test_render_has_dividers_and_full_height():
    html = render_chart_html(_payload())
    assert "border-top: 1px solid #c8ccd4" in html   # pane dividers
    assert "100dvh" in html                           # fills the dynamic viewport height


def test_render_has_indicator_toggles():
    html = render_chart_html(_payload())
    for t in ("bb", "vol", "rsi", "macd", "stoch"):
        assert f'data-toggle="{t}"' in html
    assert "applyOptions" in html        # overlay show/hide
    assert "collapsed" in html           # sub-pane collapse class


def test_render_has_educational_tooltips():
    html = render_chart_html(_payload())
    assert 'id="tip"' in html
    assert "const TIPS" in html or "TIPS = {" in html
    assert "data-tip=" in html
    assert "mouseover" in html


def test_render_omits_fundamentals_when_null():
    html = render_chart_html(_payload())  # _payload has fundamentals: None
    assert "Fundamentals (snapshot)" not in html


def test_fundamentals_reading_on_own_line():
    pay = _payload()
    pay["fundamentals"] = {"name": "NVIDIA", "sector": "Tech",
                           "valuation": {"trailing_pe": 29.48, "forward_pe": 15.13, "peg": 0.59,
                                         "reading": "P/E 29.48 — elevated (priced for growth)"},
                           "growth": {"revenue_growth_pct": 85.2, "reading": "85.2% — strong"},
                           "profitability": {"profit_margin_pct": 63.0, "reading": "63.0% — high (strong pricing power)"}}
    html = render_chart_html(pay)
    # the reading is rendered in a block-level .read element (own line), and the
    # redundant leading "P/E 29.48 — " prefix is not duplicated inline with the value
    assert "elevated (priced for growth)" in html
    assert 'class="read"' in html
    assert "white-space:normal" in html


def test_render_has_range_selection():
    html = render_chart_html(_payload())
    assert 'id="mask-left-price"' in html and 'id="mask-right-price"' in html
    assert "dim-mask" in html
    assert "shiftKey" in html
    assert "coordinateToTime" in html
    assert "timeToCoordinate" in html
    assert "clearSelection" in html


def test_selection_spans_all_panes_and_has_clear_button():
    html = render_chart_html(_payload())
    # a left+right mask for each of the 4 panes → at least 8 dim-mask elements
    assert html.count("dim-mask") >= 8
    for pane in ("price", "rsi", "macd", "stoch"):
        assert f"mask-left-{pane}" in html and f"mask-right-{pane}" in html
    # clear (X) button
    assert 'id="sel-clear"' in html
    # hover restriction references the selection bounds
    assert "sel.from" in html and "sel.to" in html


def test_render_has_moving_averages():
    html = render_chart_html(_payload())
    assert 'data-toggle="sma50"' in html and 'data-toggle="sma200"' in html
    assert "sma50" in html and "sma200" in html
    assert "MA50" in html and "MA200" in html
    # tooltip entries
    assert "golden cross" in html.lower() or "death cross" in html.lower()


def test_chip_hover_highlight():
    html = render_chart_html(_payload())
    # hover-highlight map and wiring must be present
    assert "mouseenter" in html or "mouseover" in html
    assert "lineWidth:3" in html or "lineWidth: 3" in html   # thicken on hover
    # covers the MA and bollinger targets at least
    assert "sma50S" in html and "bbU" in html


def test_panel_shift_hover_and_colored_volume():
    html = render_chart_html(_payload())
    assert "shiftHeld" in html
    assert "function renderPanel" in html or "renderPanel = " in html or "renderPanel(" in html
    assert "keydown" in html and "keyup" in html
    assert "rgba(38,166,154,0.4)" in html and "rgba(239,83,80,0.4)" in html  # colored volume


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
