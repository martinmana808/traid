# Phase 7.1 — Chart Readability & Multi-Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Fix pane x-axis sync, add vertical alignment + linked crosshair + a right info panel, and an in-chart 1h/1d/1w/1m timeframe selector, on top of Phase 7's interactive chart.

**Architecture:** Data layer pads indicator series to a full shared time domain (fixing sync) and produces a multi-resolution payload (`{resolutions: {1h,1d,1wk,1mo}, default}`). The render layer is rewritten to consume the payload: logical-range sync (now exact), fixed price-axis width, linked crosshair, a hover/summary info panel, and resolution toggle buttons.

**Tech Stack:** Python 3, pandas/numpy/yfinance (existing), TradingView `lightweight-charts@4.1.3` (CDN), pytest.

## Global Constraints

- No new Python dependencies; `lightweight-charts` from the pinned CDN `https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js`.
- Reuse existing indicator math (`tools.indicators.*`) and `tools.patterns.support_resistance`; reuse `series_from_bars`.
- All indicator series MUST have one point per bar (whitespace `{"time"}` during warm-up) so every pane shares an identical time domain.
- Resolutions: exactly `1h, 1d, 1wk, 1mo`; per-resolution lookback `1h→3mo, 1d→1y, 1wk→5y, 1mo→max`; a resolution whose fetch errors is omitted, never fatal.
- `charts/` stays gitignored. Tests run with no network (monkeypatch). Decision-support framing (not financial advice) preserved in panel/legend copy.
- Pane content unchanged: price+Bollinger+volume, RSI(14), MACD(12,26,9), Stochastic(14,3).

---

### Task 1: Whitespace-pad indicator series (fix the sync bug at the data layer)

Change `chart_data._line` to emit a whitespace point for warm-up bars instead of dropping them, so every series has one point per bar.

**Files:**
- Modify: `tools/chart_data.py` (`_line`)
- Test: `tests/test_chart_data.py`

**Interfaces:**
- `_line(dates, series)` now returns `len(dates)` points: `{"time","value"}` where defined, `{"time"}` (whitespace) where the value is None/NaN. `series_from_bars` output keys unchanged; each indicator list is now full-length.

- [ ] **Step 1: Update the failing tests**

In `tests/test_chart_data.py`, replace `test_series_shapes_and_no_nan` with:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_chart_data.py::test_indicator_series_are_full_length_with_whitespace_warmup -v`
Expected: FAIL (current `_line` drops warm-up, so `len(out["rsi"]) != 60`).

- [ ] **Step 3: Implement the change**

In `tools/chart_data.py`, replace `_line`:

```python
def _line(dates, series):
    """Zip dates with a pandas Series into one point per bar. Warm-up (NaN) bars
    become whitespace points ({time} only) so every series shares the same time
    domain as the candles — required for exact cross-pane axis sync."""
    out = []
    for d, v in zip(dates, series.tolist()):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            out.append({"time": d})
        else:
            out.append({"time": d, "value": round(float(v), 4)})
    return out
```

- [ ] **Step 4: Run tests to verify pass**

Run: `./.venv/bin/python -m pytest tests/test_chart_data.py -v`
Expected: PASS (new test + existing `test_support_resistance_present`, `build_chart_data` tests). Note `test_build_chart_data_drops_nan_bars` still holds (raw NaN bars dropped upstream).

- [ ] **Step 5: Commit**

```bash
git add tools/chart_data.py tests/test_chart_data.py
git commit -m "fix: pad indicator series with whitespace warm-up for exact pane sync"
```

---

### Task 2: Multi-resolution payload (1h/1d/1wk/1mo)

Add an `interval` param to `market.history`, then build a payload with all four resolutions.

**Files:**
- Modify: `tools/market.py` (`history`)
- Modify: `tools/chart_data.py` (append `build_chart_payload` + a resolutions table)
- Test: `tests/test_market.py`, `tests/test_chart_data.py`

**Interfaces:**
- `history(ticker, period, market=None, interval="1d")` — passes `interval=` to yfinance; otherwise identical shape `{"ticker","period","bars":[...]}` / `{"error":...}`.
- `build_chart_payload(ticker, market=None, period=None) -> dict`: `{"ticker","as_of","price","default","resolutions": {res: series_dict}}`. `RESOLUTIONS = [("1h","3mo"),("1d","1y"),("1wk","5y"),("1mo","max")]`; `period` (if given) overrides the `1d` lookback. A resolution whose `history` returns an error or <30 bars is omitted. `default = "1d"` if present else the first present resolution. `as_of`/`price` from the `default` resolution's last bar.

- [ ] **Step 1: Write failing tests**

In `tests/test_market.py`, add:

```python
import tools.market as market


def test_history_passes_interval(monkeypatch):
    captured = {}

    class FakeHist:
        def __init__(self): self.empty = False
        def iterrows(self):
            import datetime
            idx = datetime.date(2026, 1, 2)
            row = {"Open": 1.0, "High": 2.0, "Low": 0.5, "close": 1.5}
            # use a tiny stand-in row object
            class R(dict):
                pass
            r = R({"Open": 1.0, "High": 2.0, "Low": 0.5, "Close": 1.5, "Volume": 10})
            class TS:
                def date(self_): return idx
            yield TS(), r

    class FakeTicker:
        def __init__(self, sym): pass
        def history(self, period, interval="1d"):
            captured["period"] = period
            captured["interval"] = interval
            return FakeHist()

    monkeypatch.setattr(market, "_yf", lambda: type("Y", (), {"Ticker": FakeTicker}))
    out = market.history("NVDA", "1y", interval="1wk")
    assert captured["interval"] == "1wk"
    assert out["bars"][0]["close"] == 1.5
```

In `tests/test_chart_data.py`, add:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `./.venv/bin/python -m pytest tests/test_market.py::test_history_passes_interval tests/test_chart_data.py -k payload -v`
Expected: FAIL (`history` has no `interval`; `build_chart_payload` undefined).

- [ ] **Step 3: Implement**

In `tools/market.py`, change `history` signature and the yfinance call:

```python
def history(ticker, period, market=None, interval="1d"):
    sym = normalize_ticker(ticker, market)
    try:
        df = _yf().Ticker(sym).history(period=period, interval=interval)
        if df.empty:
            return error_response(f"no history for {sym} ({period}/{interval})")
        rows = [
            {
                "date": idx.date().isoformat(),
                "open": round(float(r["Open"]), 4),
                "high": round(float(r["High"]), 4),
                "low": round(float(r["Low"]), 4),
                "close": round(float(r["Close"]), 4),
                "volume": int(r["Volume"]),
            }
            for idx, r in df.iterrows()
        ]
        return {"ticker": sym, "period": period, "bars": rows}
    except Exception as e:  # noqa: BLE001
        return error_response(f"history failed for {sym}: {e}")
```

(Keep the CLI `history` subcommand as-is; it calls `history(...)` with the default interval.)

In `tools/chart_data.py`, extend the existing market import to include `normalize_ticker`:

```python
from tools.market import history, normalize_ticker  # noqa: E402
```

then append:

```python
RESOLUTIONS = [("1h", "3mo"), ("1d", "1y"), ("1wk", "5y"), ("1mo", "max")]


def build_chart_payload(ticker, market=None, period=None):
    resolutions = {}
    for res, default_period in RESOLUTIONS:
        p = period if (res == "1d" and period) else default_period
        raw = history(ticker, p, market, interval=res)
        if "error" in raw:
            continue
        bars = [b for b in raw.get("bars") or []
                if all(isinstance(b.get(k), (int, float)) and math.isfinite(b[k])
                       for k in ("open", "high", "low", "close"))]
        if len(bars) < 30:
            continue
        resolutions[res] = {"_bars_last_close": round(float(bars[-1]["close"]), 2),
                            "_bars_last_date": bars[-1]["date"],
                            **series_from_bars(bars)}
    if not resolutions:
        return {"error": f"chart: no resolutions available for {ticker}"}
    default = "1d" if "1d" in resolutions else next(iter(resolutions))
    sym = normalize_ticker(ticker, market)  # label only — no extra fetch
    as_of = resolutions[default].pop("_bars_last_date")
    price = resolutions[default].pop("_bars_last_close")
    for r in resolutions.values():
        r.pop("_bars_last_close", None)
        r.pop("_bars_last_date", None)
    return {"ticker": sym, "as_of": as_of, "price": price,
            "default": default, "resolutions": resolutions}
```

Note: the `_bars_last_*` keys are scratch values popped before return, so `resolutions[res]` ends up exactly a `series_from_bars` dict.

- [ ] **Step 4: Run tests to verify pass**

Run: `./.venv/bin/python -m pytest tests/test_market.py tests/test_chart_data.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/market.py tools/chart_data.py tests/test_market.py tests/test_chart_data.py
git commit -m "feat: build_chart_payload — 1h/1d/1wk/1mo resolutions; history interval"
```

---

### Task 3: Render rewrite A — payload consumption, exact sync, alignment, timeframe toggle

Rewrite `render_chart_html` to consume the payload, sync panes by logical range (now exact), pin price-axis width, hide middle time-axes, and add the resolution toggle. (Crosshair + panel come in Task 4.)

**Files:**
- Modify: `tools/chart_render.py` (`render_chart_html` + template)
- Test: `tests/test_chart_render.py`

**Interfaces:**
- `render_chart_html(payload, meta=None) -> str`. `payload` is `build_chart_payload`'s output. Output: self-contained HTML embedding the payload as `const DATA = <json>;`, with: container ids `price`,`rsi`,`macd`,`stoch`; a `#timeframe` button row containing a `<button data-res="…">` per present resolution (label map `1h→1H,1d→1D,1wk→1W,1mo→1M`); `minimumWidth` set on the price scales; logical-range sync code; a JS `loadResolution(res)` that setData's all series from `DATA.resolutions[res]`. Initial resolution = `DATA.default`.

**Implementation guidance (write the JS to satisfy these; pin to lightweight-charts v4 API):**
- Build the four charts as before. Apply to every chart's options: `rightPriceScale:{borderColor:'#2a2e39', minimumWidth:72}`. Set `timeScale:{visible:false}` on `price`,`rsi`,`macd` and `timeScale:{visible:true,borderColor:'#2a2e39'}` on `stoch`.
- Create the series ONCE (candles, bbU/M/L, volume, rsi, macdHist, macdLine, macdSig, kS, dS). `loadResolution(res)` calls `.setData(...)` on each from `DATA.resolutions[res]`, maps MACD histogram colors, and removes+recreates the S/R price lines (track current price-line handles in a module-level array so they can be removed). After loading, `charts.forEach(c=>c.timeScale().fitContent())`.
- Sync: `subscribeVisibleLogicalRangeChange` on each chart with a `syncing` reentrancy guard, `setVisibleLogicalRange` on the others (wrap in try/catch). This is exact now that all series share the domain.
- Toggle row: `<div id="timeframe">` with a button per present resolution; clicking sets `active` class and calls `loadResolution`. Initialize to `DATA.default`.

- [ ] **Step 1: Write failing tests**

Replace the `_data()` fixture in `tests/test_chart_render.py` with a payload-shaped one and update assertions:

```python
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
```

(Delete the old `_data()`-based `test_render_is_self_contained_html` / `test_embedded_json_roundtrips`; the two above replace them. Keep `render_session_index` tests untouched.)

- [ ] **Step 2: Run to verify fail**

Run: `./.venv/bin/python -m pytest tests/test_chart_render.py -v`
Expected: FAIL (renderer still expects the old flat `chart_data`).

- [ ] **Step 3: Implement the rewrite**

Rewrite `render_chart_html` and `_TEMPLATE` in `tools/chart_render.py` per the implementation guidance above. Build the timeframe buttons in Python from `payload["resolutions"]` keys (label map `{"1h":"1H","1d":"1D","1wk":"1W","1mo":"1M"}`), substitute via a `__TIMEFRAME__` token. Embed the whole `payload` as `const DATA = __DATA__;`. Keep the existing title/subtitle logic (now reading `payload["ticker"]`, `payload["price"]`, `payload["as_of"]`; period label can read `DATA.default`). Keep `_LEGEND`. Maintain the exact `const DATA = __DATA__;\n` line for the round-trip test.

- [ ] **Step 4: Run tests to verify pass**

Run: `./.venv/bin/python -m pytest tests/test_chart_render.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/chart_render.py tests/test_chart_render.py
git commit -m "feat: payload-based render — exact logical sync, axis alignment, timeframe toggle"
```

---

### Task 4: Render B — linked crosshair + info panel (summary + hover)

Layer the linked crosshair and the right-side info panel onto the rewritten template.

**Files:**
- Modify: `tools/chart_render.py` (template JS + a panel container/CSS)
- Test: `tests/test_chart_render.py`

**Interfaces:** no Python signature change. Output additionally contains: an info-panel container `id="panel"`; `subscribeCrosshairMove` wiring; JS helpers that compute the visible-range summary and the per-candle hover readout.

**Implementation guidance:**
- **Crosshair link:** for each chart, `subscribeCrosshairMove(param)`. When `param.time` is set, call `setCrosshairPosition(value, param.time, series)` on the *other* charts using each one's primary series and that series' value at `param.time` (look it up from a per-resolution `Map(time→value)` built in `loadResolution`). Guard reentrancy. When `param.time` is empty (mouse left), `clearCrosshairPosition()` on the others.
- **Panel — summary mode** (no hover): on `subscribeVisibleLogicalRangeChange`, take the visible candles of the current resolution; compute date-range, O=first.open, H=max(high), L=min(low), C=last.close, change%=(C/O−1)*100, and the latest *defined* value of each indicator within the visible window; render with readings (RSI 70/30, stoch 80/20, MACD hist sign, price vs BB). Also show static support/resistance and the TRaid call.
- **Panel — hover mode:** on `subscribeCrosshairMove` with a valid time, find that candle and show its O/H/L/C/Vol + each indicator's value at that time, with readings. On mouse-leave, revert to summary mode.
- **Reading helpers (JS):** `rsiRead(v)`, `stochRead(v)`, `macdRead(hist)`, `bbRead(price,upper,lower)` returning short strings; mirror Phase 7's thresholds.
- Layout: a flex row — charts column (left, flex:1) + `#panel` (right, fixed ~230px, dark, scrollable). Keep it readable; end the panel with "Context for timing — not financial advice."

- [ ] **Step 1: Write failing tests**

Add to `tests/test_chart_render.py`:

```python
def test_render_has_panel_and_crosshair_link():
    html = render_chart_html(_payload())
    assert 'id="panel"' in html
    assert "subscribeCrosshairMove" in html
    assert "setCrosshairPosition" in html
    # summary recompute is wired to range changes too
    assert html.count("subscribeVisibleLogicalRangeChange") >= 1
```

- [ ] **Step 2: Run to verify fail**

Run: `./.venv/bin/python -m pytest tests/test_chart_render.py::test_render_has_panel_and_crosshair_link -v`
Expected: FAIL (no panel/crosshair yet).

- [ ] **Step 3: Implement** per guidance (add `#panel` container + CSS, the crosshair-sync block, the summary/hover panel logic and reading helpers).

- [ ] **Step 4: Run tests to verify pass**

Run: `./.venv/bin/python -m pytest tests/test_chart_render.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/chart_render.py tests/test_chart_render.py
git commit -m "feat: linked crosshair + summary/hover info panel"
```

---

### Task 5: CLI — switch to the payload

Point `chart.py` at `build_chart_payload` and pass the payload to the renderer.

**Files:**
- Modify: `tools/chart.py` (`generate_chart`; import)
- Test: `tests/test_chart.py`

**Interfaces:** `generate_chart(...)` now calls `build_chart_payload(ticker, market, period)` and writes `render_chart_html(payload, meta)`. `write_chart` is unchanged (it already takes the data dict + meta and renders). `as_of`/`ticker`/`price` come from the payload. Snapshot/live paths unchanged.

- [ ] **Step 1: Update tests**

In `tests/test_chart.py`, change the `_data()` fixture to a payload (reuse Task 3's `_payload()` shape — copy it in) and update the call-label test to monkeypatch `chart.build_chart_payload`:

```python
def _payload():
    series = {
        "candles": [{"time": "2026-06-26", "open": 1, "high": 2, "low": 0.5, "close": 198.18}],
        "volume": [{"time": "2026-06-26", "value": 1000.0}],
        "bollinger": {"upper": [], "middle": [], "lower": []},
        "rsi": [], "macd": {"macd": [], "signal": [], "hist": []},
        "stochastic": {"k": [], "d": []}, "support": 190.0, "resistance": 205.0,
    }
    return {"ticker": "NVDA", "as_of": "2026-06-26", "price": 198.18,
            "default": "1d", "resolutions": {"1d": series}}


def test_write_chart_creates_self_contained_file(tmp_path):
    out = write_chart(_payload(), {}, str(tmp_path / "live"), "NVDA-2026-06-26.html")
    assert os.path.exists(out)
    html = open(out, encoding="utf-8").read()
    assert "lightweight-charts@4.1.3" in html
    assert "NVDA" in html


def test_write_chart_returns_path_under_out_dir(tmp_path):
    out = write_chart(_payload(), {}, str(tmp_path / "sub"), "x.html")
    assert out.endswith(os.path.join("sub", "x.html"))


def test_generate_chart_snapshot_embeds_call_label(tmp_path, monkeypatch):
    import tools.chart as chart
    pay = _payload()
    monkeypatch.setattr(chart, "build_chart_payload", lambda t, m=None, p=None: dict(pay))
    out = chart.generate_chart("NVDA", charts_root=str(tmp_path), snapshot=True,
                               call_id="2026-06-28-001",
                               call_meta={"call": "buy", "confidence": "high",
                                          "call_date": "2026-06-28"}, open_browser=False)
    html = open(out, encoding="utf-8").read()
    assert "buy" in html and "high" in html and "2026-06-28" in html
```

- [ ] **Step 2: Run to verify fail**

Run: `./.venv/bin/python -m pytest tests/test_chart.py -v`
Expected: FAIL (`generate_chart` still calls `build_chart_data`; `chart` has no `build_chart_payload`).

- [ ] **Step 3: Implement**

In `tools/chart.py`: change the import to `from tools.chart_data import build_chart_payload` (drop `build_chart_data`), and in `generate_chart` replace `data = build_chart_data(ticker, market, period)` with `data = build_chart_payload(ticker, market, period)`. The rest (`sym = data["ticker"]`, `date = data["as_of"]`, paths, `write_chart`) is unchanged because the payload still exposes `ticker`/`as_of`. `--period` passes through as `period`.

- [ ] **Step 4: Run tests + full suite**

Run: `./.venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Manual smoke (network)**

Run: `./.venv/bin/python tools/chart.py META --period 1y`
Expected: prints `{"chart": "<path>"}`, opens browser. Confirm visually: zoom OUT — all four panes stay x-aligned (the bug); hovering shows a synced vertical line + values across panes; the right panel summarizes the visible range and switches to a single candle on hover; the 1H/1D/1W/1M buttons swap candle resolution. (If headless/no network: confirm the file exists and `grep -c data-res` ≥ 1.)

- [ ] **Step 6: Commit**

```bash
git add tools/chart.py tests/test_chart.py
git commit -m "feat: chart.py uses multi-resolution payload"
```

---

### Task 6: Docs

**Files:**
- Modify: `README.md`, `.claude/skills/traid-analyst/SKILL.md`

- [ ] **Step 1:** In `README.md`'s chart block, add a line noting the chart now has linked panes, a synced crosshair, a visible-range/hover info panel, and an in-chart 1H/1D/1W/1M timeframe toggle.

- [ ] **Step 2:** In `SKILL.md` step 4's chart bullet, append: "The chart has 1H/1D/1W/1M timeframe buttons, a synced crosshair across all panes, and a right panel that summarizes the visible range (or the hovered candle)."

- [ ] **Step 3: Commit**

```bash
git add README.md .claude/skills/traid-analyst/SKILL.md
git commit -m "docs: note Phase 7.1 chart readability + timeframe toggle"
```

---

## Self-Review

**Spec coverage:** sync fix → Task 1 (data) + Task 3 (logical sync); vertical alignment → Task 3 (`minimumWidth`, hidden middle axes); linked crosshair → Task 4; info panel (summary+hover) → Task 4; timeframe selector → Task 2 (data) + Task 3 (toggle) + Task 5 (CLI). Docs → Task 6. ✓

**Placeholder scan:** data/CLI tasks carry verbatim code + tests; render tasks (large interactive JS) carry precise component specs, exact v4 API calls, token names, and structural + round-trip tests — browser behavior is manually verified in Task 5 Step 5. ✓

**Type consistency:** `build_chart_payload` output (`ticker/as_of/price/default/resolutions`) consumed by `render_chart_html(payload)` (Task 3/4) and `generate_chart` (Task 5); `resolutions[res]` is exactly a `series_from_bars` dict (scratch keys popped); `_line` full-length change (Task 1) is what makes the Task 3 logical sync exact. `history(...., interval=)` added in Task 2 and used by `build_chart_payload`. ✓
