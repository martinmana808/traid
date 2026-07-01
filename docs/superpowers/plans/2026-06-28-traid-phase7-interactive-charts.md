# Phase 7 — Interactive Charts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an interactive, TradingView-style chart tool to TRaid that renders zoomable/pannable candles + Bollinger/volume with RSI/MACD/stochastic sub-panes for any ticker, saved as self-contained HTML (live re-pull + frozen per-call snapshots).

**Architecture:** A new `tools/chart.py` CLI orchestrates three focused modules — `chart_data.py` (builds plain series dicts from OHLCV by reusing the existing `indicators.py` pure functions and a new `patterns.support_resistance` helper), `chart_render.py` (renders a self-contained HTML string embedding the data + TradingView `lightweight-charts` from CDN), and the CLI itself (fetch, write files, open browser, maintain a per-session index). No new Python dependencies.

**Tech Stack:** Python 3, pandas/numpy (existing), yfinance (existing, network only), TradingView `lightweight-charts@4.1.3` (CDN `<script>`, no install), pytest.

## Global Constraints

- No new Python dependencies — `lightweight-charts` loads from CDN; reuse yfinance/pandas/numpy only.
- Reuse existing pure functions: `tools.indicators.{rsi,macd,bollinger,stochastic}`; do not reimplement indicator math.
- Charts are personal output — `charts/` MUST be gitignored (like `data/`).
- Existing CLI output of `indicators.py` and `patterns.py` must remain byte-for-byte unchanged after refactors.
- Tests must run with no network: pure functions take in-memory fixtures; network wrappers are tested via monkeypatch.
- Tests live in `tests/test_<module>.py`, import via `from tools.x import ...` (repo root is on `sys.path` via `conftest.py`).
- CDN script URL, pinned exactly: `https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js`
- Decision-support tool, not financial advice — keep that framing in any user-facing copy.

---

### Task 1: Extract `support_resistance` helper in patterns.py

Pull the nearest support/resistance computation out of `patterns.analyze()` into a reusable, importable function so `chart_data.py` can use it without re-fetching. Behaviour of `analyze()` stays identical.

**Files:**
- Modify: `tools/patterns.py` (add function near `find_pivots`, ~line 145; refactor `analyze` ~lines 196-201)
- Test: `tests/test_patterns.py`

**Interfaces:**
- Produces: `support_resistance(highs: list[float], lows: list[float], price: float) -> dict` returning `{"support": float, "resistance": float}` (both rounded to 2 dp). Same values `analyze()` currently computes.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_patterns.py`:

```python
from tools.patterns import support_resistance


def test_support_resistance_picks_nearest_pivots():
    # rising-then-falling sawtooth produces clear pivots around price 50
    highs = [40, 45, 42, 55, 48, 60, 52, 58, 50, 54]
    lows =  [30, 35, 32, 45, 38, 50, 42, 48, 40, 44]
    sr = support_resistance(highs, lows, price=50.0)
    assert sr["resistance"] >= 50.0
    assert sr["support"] <= 50.0


def test_support_resistance_falls_back_to_extremes():
    # monotonic data: no pivot above/below price -> fall back to max high / min low
    highs = [10, 11, 12, 13, 14, 15]
    lows =  [9, 10, 11, 12, 13, 14]
    sr = support_resistance(highs, lows, price=14.5)
    assert sr["resistance"] == 15.0
    assert sr["support"] == 9.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_patterns.py::test_support_resistance_picks_nearest_pivots tests/test_patterns.py::test_support_resistance_falls_back_to_extremes -v`
Expected: FAIL with `ImportError: cannot import name 'support_resistance'`

- [ ] **Step 3: Add the function and refactor `analyze` to use it**

In `tools/patterns.py`, add after `find_pivots` (after ~line 145):

```python
def support_resistance(highs, lows, price):
    """Nearest pivot-based support/resistance around `price`, with extreme fallbacks."""
    piv = find_pivots(highs, lows, window=3)
    high_piv = [p["price"] for p in piv if p["kind"] == "high"]
    low_piv = [p["price"] for p in piv if p["kind"] == "low"]
    resistance = min([h for h in high_piv if h > price], default=max(highs))
    support = max([lo for lo in low_piv if lo < price], default=min(lows))
    return {"support": round(support, 2), "resistance": round(resistance, 2)}
```

Then in `analyze`, replace the block currently at ~lines 197-201:

```python
    # structure
    piv = find_pivots(highs, lows, window=3)
    high_piv = [p["price"] for p in piv if p["kind"] == "high"]
    low_piv = [p["price"] for p in piv if p["kind"] == "low"]
    resistance = min([h for h in high_piv if h > price], default=round(max(highs), 2))
    support = max([lo for lo in low_piv if lo < price], default=round(min(lows), 2))
```

with:

```python
    # structure
    piv = find_pivots(highs, lows, window=3)
    high_piv = [p["price"] for p in piv if p["kind"] == "high"]
    low_piv = [p["price"] for p in piv if p["kind"] == "low"]
    sr = support_resistance(highs, lows, price)
    support, resistance = sr["support"], sr["resistance"]
```

Note: the `nearest_support`/`nearest_resistance` lines in the returned dict already wrap `round(support, 2)` / `round(resistance, 2)`; rounding twice is harmless and output is unchanged.

- [ ] **Step 4: Run tests to verify they pass (incl. existing patterns tests unchanged)**

Run: `./.venv/bin/python -m pytest tests/test_patterns.py -v`
Expected: PASS (new tests pass, all pre-existing patterns tests still pass)

- [ ] **Step 5: Commit**

```bash
git add tools/patterns.py tests/test_patterns.py
git commit -m "refactor: extract reusable support_resistance() from patterns.analyze"
```

---

### Task 2: `series_from_bars` — pure chart-data builder

The network-free core: turn a list of OHLCV bar dicts into the series dicts the chart needs. Reuses `indicators` pure functions and `patterns.support_resistance`.

**Files:**
- Create: `tools/chart_data.py`
- Test: `tests/test_chart_data.py`

**Interfaces:**
- Consumes: `tools.indicators.{rsi,macd,bollinger,stochastic}`, `tools.patterns.support_resistance`.
- Produces: `series_from_bars(bars: list[dict]) -> dict`. Input bars are `{"date","open","high","low","close","volume"}` (the shape `tools.market.history` returns). Output keys: `candles` (list of `{time,open,high,low,close}`), `volume` (list of `{time,value}`), `bollinger` (`{upper,middle,lower}` each a list of `{time,value}`), `rsi` (list of `{time,value}`), `macd` (`{macd,signal,hist}` each a list of `{time,value}`), `stochastic` (`{k,d}` each a list of `{time,value}`), `support` (float), `resistance` (float). All indicator series omit NaN (warm-up) points; `time` is the bar's `date` string.

- [ ] **Step 1: Write the failing test**

Create `tests/test_chart_data.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_chart_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.chart_data'`

- [ ] **Step 3: Write the implementation**

Create `tools/chart_data.py`:

```python
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


def _line(dates, series):
    """Zip dates with a pandas Series into [{time, value}], dropping NaN warm-up."""
    out = []
    for d, v in zip(dates, series.tolist()):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/test_chart_data.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/chart_data.py tests/test_chart_data.py
git commit -m "feat: chart_data.series_from_bars — chart-ready series from OHLCV"
```

---

### Task 3: `build_chart_data` — yfinance-backed wrapper

Thin wrapper that fetches OHLCV via the existing `market.history` and feeds `series_from_bars`, adding metadata. Tested with monkeypatch (no network).

**Files:**
- Modify: `tools/chart_data.py` (append function)
- Test: `tests/test_chart_data.py`

**Interfaces:**
- Consumes: `tools.market.history(ticker, period, market) -> {"ticker","period","bars":[...]}` (or `{"error": ...}`); `series_from_bars` from Task 2.
- Produces: `build_chart_data(ticker, market=None, period="1y") -> dict` with keys `ticker, period, as_of, price` plus all `series_from_bars` keys. On failure returns `{"error": str}`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_chart_data.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_chart_data.py::test_build_chart_data_uses_market_history -v`
Expected: FAIL with `AttributeError: module 'tools.chart_data' has no attribute 'history'`

- [ ] **Step 3: Add the import and the function**

In `tools/chart_data.py`, add to the imports block:

```python
from tools.market import history  # noqa: E402
```

Append at end of file:

```python
def build_chart_data(ticker, market=None, period="1y"):
    raw = history(ticker, period, market)
    if "error" in raw:
        return raw
    bars = raw.get("bars") or []
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/test_chart_data.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/chart_data.py tests/test_chart_data.py
git commit -m "feat: chart_data.build_chart_data — yfinance-backed chart series"
```

---

### Task 4: `render_chart_html` — self-contained interactive page

Pure renderer: given chart data + metadata, return a complete HTML string embedding the data and the `lightweight-charts` CDN script. Produces the 4 synced panes.

**Files:**
- Create: `tools/chart_render.py`
- Test: `tests/test_chart_render.py`

**Interfaces:**
- Produces: `render_chart_html(chart_data: dict, meta: dict | None = None) -> str`. `meta` may contain `call`, `confidence`, `call_date` (all optional) to annotate the title. Returns full HTML (`<!doctype html>...`). Must contain the pinned CDN URL, embed `chart_data` as JSON (no `__DATA__` token left), and include container ids `price`, `rsi`, `macd`, `stoch`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_chart_render.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_chart_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.chart_render'`

- [ ] **Step 3: Write the implementation**

Create `tools/chart_render.py`:

```python
"""Renders self-contained interactive HTML charts (Phase 7).

Pure string rendering — no network, no filesystem. Embeds the chart data as
JSON and loads TradingView lightweight-charts from a pinned CDN URL.
"""
import json

CDN = "https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"

_TEMPLATE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — TRaid</title>
<script src="__CDN__"></script>
<style>
  html,body{margin:0;background:#0e0e12;color:#d1d4dc;font:13px/1.4 -apple-system,Segoe UI,Roboto,sans-serif}
  #header{padding:10px 14px;border-bottom:1px solid #1c1f2b}
  #title{font-weight:600;font-size:15px}
  #subtitle{color:#9aa0ad;margin-left:8px}
  .label{padding:2px 14px;color:#787b86;font-size:11px;text-transform:uppercase;letter-spacing:.04em}
  .pane{width:100%}
  #legend{padding:10px 14px;color:#787b86;border-top:1px solid #1c1f2b}
  #legend b{color:#9aa0ad}
</style></head><body>
<div id="header"><span id="title">__TITLE__</span><span id="subtitle">__SUBTITLE__</span></div>
<div class="label">Price · Bollinger · Volume</div><div class="pane" id="price"></div>
<div class="label">RSI (14)</div><div class="pane" id="rsi"></div>
<div class="label">MACD (12,26,9)</div><div class="pane" id="macd"></div>
<div class="label">Stochastic (14,3)</div><div class="pane" id="stoch"></div>
<div id="legend">__LEGEND__</div>
<script>
const DATA = __DATA__;
const LWC = LightweightCharts;
const dark = {layout:{background:{color:'#0e0e12'},textColor:'#d1d4dc'},
  grid:{vertLines:{color:'#15171f'},horzLines:{color:'#15171f'}},
  rightPriceScale:{borderColor:'#2a2e39'},timeScale:{borderColor:'#2a2e39'},
  crosshair:{mode:0}};
function mk(id,h){return LWC.createChart(document.getElementById(id),
  Object.assign({height:h,autoSize:true},dark));}

const price = mk('price',380);
const candles = price.addCandlestickSeries({upColor:'#26a69a',downColor:'#ef5350',
  borderVisible:false,wickUpColor:'#26a69a',wickDownColor:'#ef5350'});
candles.setData(DATA.candles);
const bbU=price.addLineSeries({color:'#5b8def',lineWidth:1});bbU.setData(DATA.bollinger.upper);
const bbM=price.addLineSeries({color:'#787b86',lineWidth:1});bbM.setData(DATA.bollinger.middle);
const bbL=price.addLineSeries({color:'#5b8def',lineWidth:1});bbL.setData(DATA.bollinger.lower);
const vol=price.addHistogramSeries({priceScaleId:'',priceFormat:{type:'volume'},color:'#2b3145'});
vol.priceScale().applyOptions({scaleMargins:{top:0.82,bottom:0}});vol.setData(DATA.volume);
if(DATA.support){candles.createPriceLine({price:DATA.support,color:'#26a69a',lineWidth:1,
  lineStyle:2,axisLabelVisible:true,title:'S '+DATA.support});}
if(DATA.resistance){candles.createPriceLine({price:DATA.resistance,color:'#ef5350',lineWidth:1,
  lineStyle:2,axisLabelVisible:true,title:'R '+DATA.resistance});}

const rsi=mk('rsi',140);
const rsiS=rsi.addLineSeries({color:'#e0a73e',lineWidth:1});rsiS.setData(DATA.rsi);
rsiS.createPriceLine({price:70,color:'#ef5350',lineStyle:2,title:'70'});
rsiS.createPriceLine({price:30,color:'#26a69a',lineStyle:2,title:'30'});

const macd=mk('macd',140);
const macdHist=macd.addHistogramSeries({});
macdHist.setData(DATA.macd.hist.map(p=>({time:p.time,value:p.value,
  color:p.value>=0?'#26a69a':'#ef5350'})));
const macdLine=macd.addLineSeries({color:'#5b8def',lineWidth:1});macdLine.setData(DATA.macd.macd);
const macdSig=macd.addLineSeries({color:'#e0a73e',lineWidth:1});macdSig.setData(DATA.macd.signal);

const stoch=mk('stoch',140);
const kS=stoch.addLineSeries({color:'#5b8def',lineWidth:1});kS.setData(DATA.stochastic.k);
const dS=stoch.addLineSeries({color:'#e0a73e',lineWidth:1});dS.setData(DATA.stochastic.d);
kS.createPriceLine({price:80,color:'#ef5350',lineStyle:2,title:'80'});
kS.createPriceLine({price:20,color:'#26a69a',lineStyle:2,title:'20'});

const charts=[price,rsi,macd,stoch];let syncing=false;
charts.forEach(src=>src.timeScale().subscribeVisibleLogicalRangeChange(range=>{
  if(syncing||!range)return;syncing=true;
  charts.forEach(dst=>{if(dst!==src)dst.timeScale().setVisibleLogicalRange(range);});
  syncing=false;}));
price.timeScale().fitContent();
</script></body></html>"""

_LEGEND = (
    "<b>How to read this:</b> scroll to zoom, drag to pan, hover for values. "
    "<b>Candles</b> green=up/red=down. <b>Bollinger</b> bands = volatility envelope "
    "(price near upper=stretched high, near lower=stretched low). "
    "<b>RSI</b> &gt;70 overbought / &lt;30 oversold. "
    "<b>MACD</b> line crossing its signal = momentum shift; histogram = the gap. "
    "<b>Stochastic</b> &gt;80 overbought / &lt;20 oversold. "
    "Dashed <b>S/R</b> lines = nearest support/resistance. "
    "Context for timing — not a buy/sell trigger. Not financial advice."
)


def render_chart_html(chart_data, meta=None):
    meta = meta or {}
    ticker = chart_data.get("ticker", "?")
    price = chart_data.get("price", "")
    as_of = chart_data.get("as_of", "")
    title = f"{ticker} · {price}"
    sub_bits = [f"as of {as_of}", f"period {chart_data.get('period', '')}"]
    if meta.get("call"):
        call_bit = f"TRaid call: {meta['call']}"
        if meta.get("confidence"):
            call_bit += f" ({meta['confidence']})"
        if meta.get("call_date"):
            call_bit += f" — {meta['call_date']}"
        sub_bits.insert(0, call_bit)
    subtitle = "  ·  ".join(b for b in sub_bits if b)
    return (
        _TEMPLATE
        .replace("__CDN__", CDN)
        .replace("__TITLE__", title)
        .replace("__SUBTITLE__", subtitle)
        .replace("__LEGEND__", _LEGEND)
        .replace("__DATA__", json.dumps(chart_data))
    )
```

Note for the implementer: the test extracts JSON between `const DATA = ` and `;\n`. The template emits exactly `const DATA = __DATA__;` followed by a newline, so the markers are stable — do not reformat that line.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/test_chart_render.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/chart_render.py tests/test_chart_render.py
git commit -m "feat: chart_render.render_chart_html — interactive lightweight-charts page"
```

---

### Task 5: `render_session_index` — per-session index page

A small dark page listing a session's charts with links. This is the "all these stocks, per session/purchase" view.

**Files:**
- Modify: `tools/chart_render.py` (append function)
- Test: `tests/test_chart_render.py`

**Interfaces:**
- Produces: `render_session_index(date: str, entries: list[dict]) -> str`. Each entry: `{"ticker": str, "call": str | None, "filename": str}`. Returns HTML linking each `filename` (relative href) labelled by ticker (+ call if present).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_chart_render.py`:

```python
from tools.chart_render import render_session_index


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_chart_render.py::test_session_index_links_each_entry -v`
Expected: FAIL with `ImportError: cannot import name 'render_session_index'`

- [ ] **Step 3: Write the implementation**

Append to `tools/chart_render.py`:

```python
def render_session_index(date, entries):
    rows = []
    for e in entries:
        label = e["ticker"]
        if e.get("call"):
            label += f' <span style="color:#787b86">— {e["call"]}</span>'
        rows.append(f'<li><a href="{e["filename"]}">{label}</a></li>')
    items = "\n".join(rows)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>TRaid charts — {date}</title>
<style>
 html,body{{margin:0;background:#0e0e12;color:#d1d4dc;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}}
 h1{{font-size:16px;padding:14px;border-bottom:1px solid #1c1f2b;margin:0}}
 ul{{list-style:none;padding:14px;margin:0}} li{{padding:6px 0}}
 a{{color:#5b8def;text-decoration:none}} a:hover{{text-decoration:underline}}
 .note{{padding:0 14px 14px;color:#787b86;font-size:12px}}
</style></head><body>
<h1>TRaid charts — session {date}</h1>
<ul>
{items}
</ul>
<div class="note">Decision-support, not financial advice.</div>
</body></html>"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/test_chart_render.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/chart_render.py tests/test_chart_render.py
git commit -m "feat: chart_render.render_session_index — per-session links page"
```

---

### Task 6: `chart.py` — CLI orchestration, file writing, browser, gitignore

Wire it together: a pure `write_chart` (filesystem only, testable) and a `generate_chart`/`main` CLI (network + browser). Add `charts/` to `.gitignore`.

**Files:**
- Create: `tools/chart.py`
- Modify: `.gitignore`
- Test: `tests/test_chart.py`

**Interfaces:**
- Consumes: `chart_data.build_chart_data` (Task 3), `chart_render.render_chart_html` (Task 4), `chart_render.render_session_index` (Task 5).
- Produces:
  - `write_chart(chart_data: dict, meta: dict, out_dir: str, filename: str) -> str` — renders + writes `<out_dir>/<filename>`, returns the full path. Creates `out_dir` if needed. No network.
  - `generate_chart(ticker, market=None, period="1y", snapshot=False, call_id=None, call_meta=None, charts_root=None, open_browser=True) -> str | dict` — fetches, writes (live or snapshot path), updates session index for snapshots, optionally opens browser; returns path or `{"error": ...}`.
  - `main(argv=None)` — argparse CLI.

- [ ] **Step 1: Write the failing test**

Create `tests/test_chart.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_chart.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.chart'`

- [ ] **Step 3: Write the implementation**

Create `tools/chart.py`:

```python
"""Interactive chart CLI for TRaid (Phase 7 — the 'Screen').

Generates a self-contained, zoomable/pannable TradingView-style HTML chart for a
ticker. Two modes:
  - live (default): fresh data -> charts/live/<TICKER>-<date>.html
  - snapshot:       frozen per-call copy -> charts/sessions/<date>/<TICKER>-<callid>.html

Usage:
    python tools/chart.py NVDA
    python tools/chart.py AIR --market NZX --period 2y
    python tools/chart.py META --snapshot --call-id 2026-06-28-001

Charts are personal output and gitignored. Decision-support, not financial advice.
"""
import argparse
import json
import os
import sys
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.chart_data import build_chart_data  # noqa: E402
from tools.chart_render import render_chart_html, render_session_index  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def write_chart(chart_data, meta, out_dir, filename):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render_chart_html(chart_data, meta))
    return path


def _update_session_index(session_dir, date):
    """Rebuild index.html from the chart files present in a session dir."""
    entries = []
    for fn in sorted(os.listdir(session_dir)):
        if fn.endswith(".html") and fn != "index.html":
            ticker = fn.split("-", 1)[0]
            entries.append({"ticker": ticker, "call": None, "filename": fn})
    with open(os.path.join(session_dir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(render_session_index(date, entries))


def generate_chart(ticker, market=None, period="1y", snapshot=False,
                   call_id=None, call_meta=None, charts_root=None, open_browser=True):
    charts_root = charts_root or os.path.join(_ROOT, "charts")
    data = build_chart_data(ticker, market, period)
    if "error" in data:
        return data
    sym = data["ticker"]
    date = data["as_of"]
    meta = call_meta or {}

    if snapshot:
        session_dir = os.path.join(charts_root, "sessions", date)
        suffix = call_id or "snapshot"
        path = write_chart(data, meta, session_dir, f"{sym}-{suffix}.html")
        _update_session_index(session_dir, date)
    else:
        path = write_chart(data, meta, os.path.join(charts_root, "live"),
                           f"{sym}-{date}.html")

    if open_browser:
        webbrowser.open("file://" + os.path.abspath(path))
    return path


def main(argv=None):
    p = argparse.ArgumentParser(description="TRaid interactive chart")
    p.add_argument("ticker")
    p.add_argument("--market", default=None)
    p.add_argument("--period", default="1y")
    p.add_argument("--snapshot", action="store_true",
                   help="save a frozen per-call snapshot under charts/sessions/<date>/")
    p.add_argument("--call-id", default=None, help="ledger call id to tag a snapshot")
    args = p.parse_args(argv)
    result = generate_chart(args.ticker, args.market, args.period,
                            snapshot=args.snapshot, call_id=args.call_id)
    if isinstance(result, dict) and "error" in result:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps({"chart": result}, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/test_chart.py -v`
Expected: PASS

- [ ] **Step 5: Add `charts/` to `.gitignore`**

In `.gitignore`, under the "Personal data" section, add:

```
# Generated charts — personal output, never commit
charts/
```

- [ ] **Step 6: Run the full test suite**

Run: `./.venv/bin/python -m pytest -q`
Expected: PASS (all pre-existing + new tests)

- [ ] **Step 7: Manual smoke (network) — verify the real chart**

Run: `./.venv/bin/python tools/chart.py NVDA`
Expected: prints `{"chart": "<path>/charts/live/NVDA-<date>.html"}` and opens the browser. Confirm visually: candles render; Bollinger/volume on the price pane; RSI/MACD/stochastic panes below; scroll zooms, drag pans, all panes move together; S/R dashed lines show. (If headless/no browser, just confirm the file exists and is non-empty.)

- [ ] **Step 8: Commit**

```bash
git add tools/chart.py tests/test_chart.py .gitignore
git commit -m "feat: chart.py CLI — write/open interactive charts, session snapshots"
```

---

### Task 7: Document the chart tool (SKILL.md + README)

Make TRaid (and Martin) aware the tool exists, so it's offered during technical/timing discussions.

**Files:**
- Modify: `.claude/skills/traid-analyst/SKILL.md` (the technicals step, ~step 4)
- Modify: `README.md` (Tools section)

**Interfaces:** none (docs only).

- [ ] **Step 1: Add the chart tool to SKILL.md**

In `.claude/skills/traid-analyst/SKILL.md`, inside step 4 ("Check technicals for timing/entry/swing decisions"), append a bullet:

```markdown
   - For a visual, interactive read (candles + Bollinger/volume + RSI/MACD/stochastic he can zoom/pan and ask about), generate a chart: `./.venv/bin/python tools/chart.py <TICKER> [--market NZX] [--period 1y]`. It opens a self-contained HTML chart in his browser. When logging a concrete call, also save a frozen snapshot tied to it: `./.venv/bin/python tools/chart.py <TICKER> --snapshot --call-id <id>`. Offer the chart when he's weighing an entry or wants to learn what the indicators mean.
```

- [ ] **Step 2: Add the chart tool to README.md**

In `README.md`, in the Tools section (after the `patterns.py` block), add:

```markdown
# Interactive chart: zoomable/pannable candles + Bollinger/volume with
# RSI/MACD/stochastic sub-panes. Self-contained HTML (TradingView lightweight-charts).
# Live re-pull, or a frozen per-call snapshot. Charts are gitignored (local only).
./.venv/bin/python tools/chart.py NVDA
./.venv/bin/python tools/chart.py AIR --market NZX --period 2y
./.venv/bin/python tools/chart.py META --snapshot --call-id 2026-06-28-001
```

- [ ] **Step 3: Commit**

```bash
git add README.md .claude/skills/traid-analyst/SKILL.md
git commit -m "docs: document the interactive chart tool (chart.py)"
```

---

## Self-Review

**Spec coverage:**
- Interactive zoom/pan candles + Bollinger/volume + RSI/MACD/stochastic panes → Task 4 (template) ✓
- Reuse indicators.py / patterns.py / market.py → Tasks 1-3 ✓
- Required refactor (extract support/resistance) → Task 1 ✓
- Self-contained HTML + CDN, no new deps → Task 4 + Global Constraints ✓
- Snapshot + live re-pull modes → Task 6 (`generate_chart`) ✓
- Per-session index ("all these stocks, per session/purchase") → Tasks 5 + 6 ✓
- `charts/` gitignored → Task 6 Step 5 ✓
- "What am I looking at" legend (learning aid) → Task 4 (`_LEGEND`) ✓
- Title shows call + confidence + date when tied to a call → Task 4 (`render_chart_html` meta) ✓
- Testing: unit (data builder, renderer) + smoke (file written) → Tasks 2-6; browser interactivity manual → Task 6 Step 7 ✓
- Discoverability (SKILL.md/README) → Task 7 ✓
- Out-of-scope items (hosted/phone, auto-refresh, drawing tools) correctly omitted ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code; test code is concrete. ✓

**Type consistency:** `series_from_bars` output keys consumed identically by `render_chart_html` (`DATA.candles`, `DATA.bollinger.{upper,middle,lower}`, `DATA.macd.{macd,signal,hist}`, `DATA.stochastic.{k,d}`, `DATA.support`, `DATA.resistance`). `build_chart_data` adds `ticker/period/as_of/price` used by the renderer title. `write_chart(chart_data, meta, out_dir, filename)` signature matches its callers in `generate_chart`. `support_resistance` signature consistent between Task 1 (definition) and Task 2 (use). ✓
