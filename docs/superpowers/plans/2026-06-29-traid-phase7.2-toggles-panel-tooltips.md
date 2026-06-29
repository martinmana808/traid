# Phase 7.2 — Toggles, Richer Panel, Tooltips Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add per-graph indicator toggles, a richer right panel (derived stats + a fundamentals block), and educational hover-tooltips to the interactive chart.

**Architecture:** Data layer adds an ATR series and a fundamentals snapshot to the payload. Render layer adds top-left toggle chips per graph (overlay-hide on price, pane-collapse on sub-panes, with sync/crosshair skipping hidden panes), extends the info panel, and adds a tooltip system over the panel labels.

**Tech Stack:** Python 3, pandas/numpy/yfinance (existing), lightweight-charts@4.1.3 (CDN), pytest.

## Global Constraints

- No new Python deps; CDN pinned `https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js`.
- Reuse existing math: `tools.indicators.atr`, `tools.fundamentals.analyze`. Reuse `series_from_bars`.
- Indicator series stay one-point-per-bar (whitespace warm-up). Payload contract additions are backward-compatible (new keys only).
- `charts/` gitignored; tests no-network (monkeypatch); decision-support framing preserved.
- Default state: all indicators ON; toggling never breaks axis sync or the crosshair.

---

### Task 1: Add ATR series to `series_from_bars`

**Files:** Modify `tools/chart_data.py`; Test `tests/test_chart_data.py`.

**Interfaces:** `series_from_bars` output gains key `atr` — a full-length `_line` list (whitespace warm-up) from `tools.indicators.atr(highs, lows, closes)`.

- [ ] **Step 1: Failing test** — add to `tests/test_chart_data.py`:

```python
def test_series_includes_atr_full_length():
    out = series_from_bars(_bars(60))
    assert "atr" in out
    assert len(out["atr"]) == 60
    assert [p["time"] for p in out["atr"]] == [c["time"] for c in out["candles"]]
    assert any("value" in p for p in out["atr"])
```

- [ ] **Step 2: Run → fail.** `./.venv/bin/python -m pytest tests/test_chart_data.py::test_series_includes_atr_full_length -v` → KeyError/assert fail.

- [ ] **Step 3: Implement.** In `tools/chart_data.py`, extend the indicators import:

```python
from tools.indicators import rsi, macd, bollinger, stochastic, atr  # noqa: E402
```

In `series_from_bars`, after the `stochastic` line, add the atr series and include it in the returned dict:

```python
    atr_series = atr(highs, lows, closes)
```

and in the return dict add (next to `"stochastic"`):

```python
        "atr": _line(dates, atr_series),
```

- [ ] **Step 4: Run → pass.** `./.venv/bin/python -m pytest tests/test_chart_data.py -v`

- [ ] **Step 5: Commit.** `git add tools/chart_data.py tests/test_chart_data.py && git commit -m "feat: add ATR series to chart data"`

---

### Task 2: Embed fundamentals snapshot in `build_chart_payload`

**Files:** Modify `tools/chart_data.py`; Test `tests/test_chart_data.py`.

**Interfaces:** `build_chart_payload` returns an extra top-level key `fundamentals`: the dict from `tools.fundamentals.analyze(ticker, market)`, or `None` if it returns `{"error":...}` or raises. Never fatal.

- [ ] **Step 1: Failing tests** — add to `tests/test_chart_data.py`:

```python
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
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement.** In `tools/chart_data.py`, add an import (aliased to keep the monkeypatch target stable):

```python
from tools.fundamentals import analyze as fundamentals_analyze  # noqa: E402
```

In `build_chart_payload`, before the final `return`, compute the snapshot and add it to the returned dict:

```python
    try:
        f = fundamentals_analyze(ticker, market)
    except Exception:  # noqa: BLE001 — fundamentals are optional, never fatal
        f = None
    fundamentals = None if (not f or "error" in f) else f
```

and add `"fundamentals": fundamentals,` to the returned dict.

- [ ] **Step 4: Run → pass** (full `tests/test_chart_data.py`).

- [ ] **Step 5: Commit.** `git add tools/chart_data.py tests/test_chart_data.py && git commit -m "feat: embed fundamentals snapshot in chart payload"`

---

### Task 3: Per-graph indicator toggles (overlays + pane collapse)

**Files:** Modify `tools/chart_render.py` (template CSS + JS); Test `tests/test_chart_render.py`.

**Requirements:**
- Top-left chip cluster on each graph. On **price**: `BB` and `Vol` chips. On **rsi/macd/stoch**: a single collapse chip each (label text = `RSI`/`MACD`/`STOCH`).
- Markup: each chip is a `<span class="tog" data-toggle="bb|vol|rsi|macd|stoch">`. Position the cluster absolutely at the top-left inside each pane (so it floats over the chart), or in the label row — either way it must render the `data-toggle` attributes.
- **BB / Vol:** clicking calls `bbU/bbM/bbL.applyOptions({visible})` (all three) / `vol.applyOptions({visible})`; toggles an `off` class on the chip. Default visible.
- **rsi/macd/stoch:** clicking toggles a `collapsed` class on that pane element (`#rsi`/`#macd`/`#stoch`) whose CSS is `flex:0 0 0; min-height:0; height:0; overflow:hidden`. While collapsed, the pane's chart is removed from the sync `charts` array and the crosshair `paneEntries` (so `getVisibleLogicalRange`/crosshair don't touch a 0-size chart); re-adding on expand, then `fitContent()` all visible charts. Keep a `visibleCharts()` helper used by the sync + crosshair loops instead of the raw full array.
- Default: nothing collapsed, BB/Vol on. Don't break the timeframe toggle, logical sync, crosshair, or panel.

**Implementation guidance:** keep a module-level `paneState = {rsi:true,macd:true,stoch:true}` and derive the active charts list from it each time the sync/crosshair handlers run (don't capture a stale array). For BB/Vol keep `series.applyOptions`. After any collapse/expand, call `charts of visible panes → fitContent()`.

- [ ] **Step 1: Failing test** — add to `tests/test_chart_render.py`:

```python
def test_render_has_indicator_toggles():
    html = render_chart_html(_payload())
    for t in ("bb", "vol", "rsi", "macd", "stoch"):
        assert f'data-toggle="{t}"' in html
    assert "applyOptions" in html        # overlay show/hide
    assert "collapsed" in html           # sub-pane collapse class
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** per requirements/guidance.
- [ ] **Step 4: Run → pass** (full `tests/test_chart_render.py`).
- [ ] **Step 5: Commit.** `git add tools/chart_render.py tests/test_chart_render.py && git commit -m "feat: per-graph indicator toggles (overlay hide + pane collapse)"`

---

### Task 4: Richer info panel (derived stats + fundamentals block)

**Files:** Modify `tools/chart_render.py`; Test `tests/test_chart_render.py`.

**Requirements (extend the existing summary + hover panel):**
- **Summary mode additions** (JS, current resolution's visible candles unless noted): visible high & low + **% below high**; latest **volume vs trailing average** (×); latest **ATR** (from `DATA.resolutions[res].atr`) + **% of price**; **Bollinger %B** at right edge; **% distance to support and to resistance**. (Visible-range % change already present.)
- **Fundamentals block** from `DATA.fundamentals` (static): if present, render name · sector, then P/E, forward P/E, **PEG**, profit margin, revenue growth with each `reading`. If `DATA.fundamentals` is null, omit the block. Header: "Fundamentals (snapshot)".
- Hover mode unchanged except it may also show ATR at the hovered bar.
- Use the existing `fmt`/reading helpers; add small helpers as needed. Keep "not financial advice".

- [ ] **Step 1: Failing test** — add to `tests/test_chart_render.py`:

```python
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
```

Also extend `_payload()` in `tests/test_chart_render.py` so each resolution's series includes an `atr` key (mirror the `rsi` shape) and a top-level `"fundamentals": None`, so existing tests still construct a valid payload.

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** the extra stats + fundamentals rendering.
- [ ] **Step 4: Run → pass.**
- [ ] **Step 5: Commit.** `git add tools/chart_render.py tests/test_chart_render.py && git commit -m "feat: richer info panel — ATR/%B/range stats + fundamentals block"`

---

### Task 5: Educational tooltips on panel labels

**Files:** Modify `tools/chart_render.py`; Test `tests/test_chart_render.py`.

**Requirements:**
- A JS `TIPS` object mapping metric keys → 1–3 sentence plain-English explanations for: `rsi, macd, bollinger, percentb, stochastic, atr, volume, sr, pe, forwardpe, peg, margin, growth, change, fromhigh`. Honest about limits ("context, not a predictor").
- Every panel label/metric that has an explanation carries `data-tip="<key>"`.
- One tooltip container `<div id="tip">` (absolute, dark, ~260px, padded, hidden by default). On `mouseover` of any element with `[data-tip]`, populate `#tip` from `TIPS[key]` and position it near the cursor; on `mouseout`, hide it. Use event delegation on the panel.
- Don't interfere with the hover/summary panel logic or the chart crosshair.

- [ ] **Step 1: Failing test** — add to `tests/test_chart_render.py`:

```python
def test_render_has_educational_tooltips():
    html = render_chart_html(_payload())
    assert 'id="tip"' in html
    assert "const TIPS" in html or "TIPS = {" in html
    assert "data-tip=" in html
    assert "mouseover" in html
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** the TIPS dict, `data-tip` attributes, and the `#tip` hover system.
- [ ] **Step 4: Run → pass, then full suite** `./.venv/bin/python -m pytest -q`.
- [ ] **Step 5: Manual smoke (network):** `./.venv/bin/python tools/chart.py NVDA` — confirm: BB/Vol chips hide those overlays; RSI/MACD/Stoch chips collapse their panes (others grow) and sync/crosshair still work; the panel shows the new stats + a fundamentals block; hovering panel labels shows rich tooltips. (Headless: confirm file + `grep -c data-toggle` ≥ 5 and `data-tip`.)
- [ ] **Step 6: Commit.** `git add tools/chart_render.py tests/test_chart_render.py && git commit -m "feat: educational hover-tooltips on info-panel labels"`

---

### Task 6: Docs

**Files:** Modify `README.md`, `.claude/skills/traid-analyst/SKILL.md`.

- [ ] **Step 1:** README chart block: note per-graph indicator toggles, the richer panel (ATR/%B/range stats + a fundamentals snapshot), and educational hover-tooltips.
- [ ] **Step 2:** SKILL.md step-4 chart bullet: append that the chart has per-indicator on/off toggles, a fundamentals snapshot + volatility/range stats in the side panel, and hover-tooltips explaining each metric.
- [ ] **Step 3: Commit.** `git add README.md .claude/skills/traid-analyst/SKILL.md && git commit -m "docs: note Phase 7.2 toggles, richer panel, tooltips"`

---

## Self-Review

**Spec coverage:** per-graph toggles → Task 3; richer panel (stats) → Task 4; fundamentals block → Task 2 (data) + Task 4 (render); ATR stat → Task 1 (data) + Task 4 (render); tooltips → Task 5; docs → Task 6. ✓

**Placeholder scan:** data tasks carry verbatim code + tests; render tasks carry precise requirements + structural tests, browser behavior manually verified in Task 5 Step 5. ✓

**Type consistency:** new payload keys (`series.atr`, top-level `fundamentals`) added in Tasks 1–2 and consumed by Task 4's render; `_payload()` test fixture updated in Task 4 to include `atr` + `fundamentals` so all render tests build a valid payload; toggles (Task 3) and tooltips (Task 5) are additive to the template and must not break the Task 3 sync/crosshair handlers (the `visibleCharts()`/`paneState` approach keeps the sync array fresh). ✓
