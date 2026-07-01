# Phase 7.5 — 50/200-day Moving Averages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Checkbox steps.

**Goal:** Draw the 50-day and 200-day simple moving averages on the price pane, with per-graph on/off toggles + tooltips, and a golden/death-cross trend read in the side panel.

**Architecture:** Data layer adds `sma50`/`sma200` series to the payload (reusing `indicators.sma`). Render layer draws two line series on the price pane, wires them into `loadResolution`, adds toggle chips + tooltips, and a trend row in the panel.

## Global Constraints
- No new Python deps; reuse `tools.indicators.sma`; lightweight-charts v4; pure render; `const DATA = __DATA__;\n` intact.
- Series stay one-point-per-bar (whitespace warm-up) — an SMA is whitespace until it has enough bars (e.g. 200), which is fine (line just starts later / not at all for short histories).
- Don't break: timeframe toggle, per-graph toggles/collapse, selection+masks, crosshair, tooltips, panel.

---

### Task 1: Add sma50 / sma200 series to the payload

**Files:** Modify `tools/chart_data.py`; Test `tests/test_chart_data.py`.

**Interfaces:** `series_from_bars` output gains `sma50` and `sma200` — full-length `_line` lists from `tools.indicators.sma(closes, 50)` and `sma(closes, 200)`.

- [ ] **Step 1: Failing test** — add to `tests/test_chart_data.py`:

```python
def test_series_includes_moving_averages():
    out = series_from_bars(_bars(60))
    assert "sma50" in out and "sma200" in out
    assert len(out["sma50"]) == 60 and len(out["sma200"]) == 60
    assert [p["time"] for p in out["sma50"]] == [c["time"] for c in out["candles"]]
    # with only 60 bars, sma50 has some defined points, sma200 has none (all whitespace)
    assert any("value" in p for p in out["sma50"])
    assert all("value" not in p for p in out["sma200"])
```

- [ ] **Step 2: Run → fail.** `./.venv/bin/python -m pytest tests/test_chart_data.py::test_series_includes_moving_averages -v`

- [ ] **Step 3: Implement.** In `tools/chart_data.py` extend the indicators import to include `sma`:

```python
from tools.indicators import rsi, macd, bollinger, stochastic, atr, sma  # noqa: E402
```

and add to the `series_from_bars` return dict (next to `"atr"`):

```python
        "sma50": _line(dates, sma(closes, 50)),
        "sma200": _line(dates, sma(closes, 200)),
```

- [ ] **Step 4: Run → pass** (full `tests/test_chart_data.py`).
- [ ] **Step 5: Commit.** `git add tools/chart_data.py tests/test_chart_data.py && git commit -m "feat: add 50/200-day SMA series to chart data"`

---

### Task 2: Draw the MAs on the chart + toggles + tooltips + trend row

**Files:** Modify `tools/chart_render.py`; Test `tests/test_chart_render.py`.

**Requirements:**
1. **Two line series on the price pane:** `sma50S` (amber, e.g. `#e0a73e`, lineWidth 2) and `sma200S` (purple, e.g. `#b39ddb`, lineWidth 2) — created ONCE, distinct from the Bollinger blue/gray. In `loadResolution`, `sma50S.setData(d.sma50)` and `sma200S.setData(d.sma200)`.
2. **Toggle chips** on the price pane's `.tog-cluster`: `<span class="tog" data-toggle="sma50">MA50</span>` and `data-toggle="sma200">MA200`. Clicking toggles the series `applyOptions({visible})` + the chip `off` class (mirror the BB/Vol handling). Default ON.
3. **Tooltips:** add `TIPS` entries under keys `sma50` and `sma200` — plain-English: a moving average smooths price to show trend; the 50-day is medium-term, the 200-day is the long-term trend line (price above 200-day = healthier); when the 50 crosses above the 200 it's a "golden cross" (bullish), below = "death cross" (bearish). Honest: it's a lagging trend gauge, not a predictor.
4. **Panel trend row(s):** in `updateSummaryPanel` (and optionally hover), add rows for `MA50` and `MA200` (latest defined value in the window, via the existing `lastDefinedInRange`), plus a **Trend** row: if both defined, "Golden cross (50>200)" when sma50>sma200 else "Death cross (50<200)"; if sma200 undefined (short history) show "—". Give these rows `data-tip="sma50"` / `"sma200"`. Keep the not-financial-advice framing.

**Guidance:** series created once (not in loadResolution). Toggle handler: extend the existing `.tog` click delegation to handle `sma50`/`sma200` alongside `bb`/`vol`. Keep everything else intact.

- [ ] **Step 1: Failing test** — add to `tests/test_chart_render.py` (and update `_payload()` so each resolution's series includes `sma50`/`sma200` — mirror the `rsi` shape — so the render finds them):

```python
def test_render_has_moving_averages():
    html = render_chart_html(_payload())
    assert 'data-toggle="sma50"' in html and 'data-toggle="sma200"' in html
    assert "sma50" in html and "sma200" in html
    assert "MA50" in html and "MA200" in html
    # tooltip entries
    assert "golden cross" in html.lower() or "death cross" in html.lower()
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** the two line series, loadResolution wiring, toggle chips + handler, TIPS entries, and the panel MA50/MA200/Trend rows. Update `_payload()` fixture to include `sma50`/`sma200` per resolution.
- [ ] **Step 4: Run → pass, then full suite** `./.venv/bin/python -m pytest -q`.
- [ ] **Step 5: Manual smoke (network):** `./.venv/bin/python tools/chart.py NVDA` — confirm two MA lines on the price pane, MA50/MA200 chips toggle them, hovering the chips/labels shows tooltips, and the panel shows MA50/MA200 + a golden/death-cross trend read. (Headless: `grep -c 'data-toggle="sma50"'`.)
- [ ] **Step 6: Commit.** `git add tools/chart_render.py tests/test_chart_render.py && git commit -m "feat: draw 50/200-day MAs on price pane with toggles, tooltips, trend row"`

---

### Task 3: Docs

**Files:** `README.md`, `.claude/skills/traid-analyst/SKILL.md`.

- [ ] **Step 1:** README chart block: note 50/200-day moving averages on the price chart (toggleable) + a golden/death-cross trend read in the panel.
- [ ] **Step 2:** SKILL.md chart bullet: same concise note.
- [ ] **Step 3: Commit.** `git add README.md .claude/skills/traid-analyst/SKILL.md && git commit -m "docs: note Phase 7.5 moving averages"`

---

## Self-Review
Spec coverage: sma50/200 data → Task 1; drawn lines + toggles + tooltips + trend row → Task 2; docs → Task 3. Type consistency: new payload keys `sma50`/`sma200` (Task 1) consumed by Task 2's render + `_payload()` fixture updated; toggle handling mirrors existing BB/Vol; panel uses existing `lastDefinedInRange`. Placeholder scan: data task verbatim; render task concrete requirements + structural test; browser verified in Task 2 Step 5.
