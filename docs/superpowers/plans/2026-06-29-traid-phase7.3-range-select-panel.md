# Phase 7.3 — Range Selection + Panel Layout Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Fix the cramped/overflowing info panel (fundamentals rows), and add Shift+drag range selection that dims candles outside the selection and recomputes the panel over the selected period.

**Architecture:** Both changes are in `tools/chart_render.py`. Panel: restructure fundamentals rows so readings sit on their own line. Selection: a `sel={from,to}|null` state, two dim-mask overlays on the price pane repositioned on range change, Shift+drag handlers, and a windowed summary computation reused for both visible-range and selected-range.

**Tech Stack:** Python 3 (pure render), TradingView lightweight-charts@4.1.3 (CDN), pytest.

## Global Constraints

- No new Python deps; CDN pinned @4.1.3. Pure render function; `const DATA = __DATA__;\n` intact.
- All new listeners wired once at top level (NOT inside `loadResolution`). On resolution switch, clear any active selection and hide masks (candle times differ per resolution).
- `data-tip` tooltips remain on all panel labels. Tests no-network. Not-financial-advice framing kept.
- Masks: `pointer-events:none`, only over the price pane, above the canvas but below the toggle chips.

---

### Task 1: Fix the info-panel layout (fundamentals overflow + breathing room)

**Files:** Modify `tools/chart_render.py`; Test `tests/test_chart_render.py`.

**Problem:** Fundamentals rows render label + value + the full classifier reading on one ~230px row, so long readings (e.g. "P/E 29.48 — elevated (priced for growth)") wrap over the value and overlap.

**Requirements:**
- Restructure each fundamentals metric (in `_make_fund_block_html`) to: a label+value row (`.row` with `.key`/`.val`), then the classifier reading on its OWN full-width line beneath (a `.read` block — muted, smaller, `white-space:normal`, wraps). No value appears twice on one line — if the reading begins by repeating the label+value (e.g. "P/E 29.48 — …"), strip that leading "`<label> <value> — `" prefix and show only the descriptive tail; if stripping is awkward, just show the reading on its own line (acceptable).
- Add modest vertical rhythm: ensure `.read` has a small top margin and the rows don't collide. Keep the existing section separators (`.sep`) and the `data-tip` attributes on the labels.
- Indicator rows (short tags like "Neutral"/"Bearish") may stay as label · value · tag — only the long fundamentals readings need their own line. (If any indicator `.read` also overflows, give `.read` `white-space:normal` globally so it wraps under instead of overlapping.)

**Implementation guidance:** add/adjust CSS — e.g. `#panel .read{display:block;color:#e0a73e;font-size:11px;white-space:normal;margin:1px 0 4px}` and make the fundamentals `frow` emit `<div class="row">…</div><div class="read" ...>READING_TAIL</div>` instead of a 3-column row. A small JS/Python helper to strip the `"<label> <value> — "` prefix from a reading is fine (e.g. split on `' — '` and take the tail).

- [ ] **Step 1: Failing test** — add to `tests/test_chart_render.py`:

```python
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
```

- [ ] **Step 2: Run → fail.** `./.venv/bin/python -m pytest tests/test_chart_render.py::test_fundamentals_reading_on_own_line -v`
- [ ] **Step 3: Implement** the `_make_fund_block_html` restructure + CSS.
- [ ] **Step 4: Run → pass** (full `tests/test_chart_render.py`).
- [ ] **Step 5: Commit.** `git add tools/chart_render.py tests/test_chart_render.py && git commit -m "fix: info panel — fundamentals readings on their own line, no overflow"`

---

### Task 2: Shift+drag range selection (dim outside + panel reflects selection)

**Files:** Modify `tools/chart_render.py`; Test `tests/test_chart_render.py`.

**Requirements:**
- **Windowed summary:** refactor `updateSummaryPanel()` so the O/H/L/C/change/high/low/%-from-high/
  vol-avg/ATR/%B/S-R-distance/indicator-latest computations run over a `[loIdx, hiIdx]` window. When
  `sel` is null → use the price chart's visible logical range (current behavior). When `sel` is set →
  use the indices of the selected candle range. Header shows "SELECTION  <from> → <to>" when active,
  else the existing summary header.
- **State:** module-level `let sel = null;` ( `{from, to}` times, ordered). A `clearSelection()` hides
  masks, sets `sel=null`, calls `updateSummaryPanel()`.
- **Masks:** two divs `<div id="mask-left" class="dim-mask"></div><div id="mask-right" class="dim-mask"></div>`
  inside the price pane. CSS `.dim-mask{position:absolute;top:0;bottom:0;background:rgba(14,14,18,0.6);
  pointer-events:none;z-index:3;display:none}`. A `positionMasks()` reads
  `price.timeScale().timeToCoordinate(sel.from)` and `…(sel.to)`; left mask spans `left:0` to that-x,
  right mask spans that-x to the pane's right edge; clamp to pane width; hide masks when `sel` null.
  Call `positionMasks()` inside the sync `subscribeVisibleLogicalRangeChange` handler (after the existing
  body) and after `fitContent`/resolution switch.
- **Drag handlers** on the price pane element (`document.getElementById('price')`):
  - `mousedown`: if `e.shiftKey` → `dragging=true`, `dragStartX = e.offsetX` (relative to pane),
    `e.preventDefault()` to suppress the chart's own pan; record `dragStartTime =
    price.timeScale().coordinateToTime(dragStartX)`. If NOT shiftKey → `clearSelection()` (plain click
    clears) and let the chart handle normal drag.
  - `mousemove` (while `dragging`): compute current x, set a provisional `sel` from
    `coordinateToTime(min)`/`coordinateToTime(max)` and live-call `positionMasks()` (show masks).
  - `mouseup` (while `dragging`): finalize `sel` (ordered from/to; if the drag was a tiny click <~3px,
    treat as a clear), `dragging=false`, `updateSummaryPanel()`. Attach mousemove/mouseup on
    `document` during a drag (or on the pane) so a drag that leaves the pane still completes.
  - Guard: if `coordinateToTime` returns null (drag outside data), clamp to first/last candle time.
- **Resolution switch:** `loadResolution` calls `clearSelection()` (times differ per resolution).
- Wire all handlers ONCE at top level. Don't break toggles, crosshair, tooltips, timeframe, or the
  Task 1 panel.

- [ ] **Step 1: Failing test** — add to `tests/test_chart_render.py`:

```python
def test_render_has_range_selection():
    html = render_chart_html(_payload())
    assert 'id="mask-left"' in html and 'id="mask-right"' in html
    assert "dim-mask" in html
    assert "shiftKey" in html
    assert "coordinateToTime" in html
    assert "timeToCoordinate" in html
    assert "clearSelection" in html
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** the windowed summary, masks, drag handlers, and resolution-switch clear.
- [ ] **Step 4: Run → pass, then full suite** `./.venv/bin/python -m pytest -q`.
- [ ] **Step 5: Manual smoke (network):** `./.venv/bin/python tools/chart.py NVDA` — confirm: Shift+drag
  on the price chart selects a band, candles outside dim to ~40%, the panel header shows SELECTION with
  the date range and all stats reflect the selected candles; the masks stay aligned when you pan/zoom;
  a plain click clears it; switching timeframe clears it. (Headless: confirm file + `grep -c dim-mask`.)
- [ ] **Step 6: Commit.** `git add tools/chart_render.py tests/test_chart_render.py && git commit -m "feat: Shift+drag range selection — dim outside + panel reflects selected period"`

---

### Task 3: Docs

**Files:** Modify `README.md`, `.claude/skills/traid-analyst/SKILL.md`.

- [ ] **Step 1:** README chart block: note Shift+drag to select a period (dims the rest; panel + stats reflect the selection; click to clear).
- [ ] **Step 2:** SKILL.md step-4 chart bullet: append "Shift+drag on the price chart selects a period — the rest dims and the side-panel stats recompute for just that range."
- [ ] **Step 3: Commit.** `git add README.md .claude/skills/traid-analyst/SKILL.md && git commit -m "docs: note Phase 7.3 range selection + panel layout fix"`

---

## Self-Review

**Spec coverage:** panel overflow fix → Task 1; Shift+drag selection + dim masks + windowed panel +
clear + resolution-switch-clear → Task 2; docs → Task 3. ✓

**Placeholder scan:** Task 1 has concrete CSS/markup guidance + a structural test; Task 2 has concrete
handler/mask/window guidance + structural test; browser behavior manually verified in Task 2 Step 5. ✓

**Type consistency:** `updateSummaryPanel` becomes window-parameterized (visible range vs `sel` indices)
— used by the sync handler, `loadResolution`, and the drag `mouseup`; `clearSelection()` defined in
Task 2 and called from `loadResolution`; masks `#mask-left`/`#mask-right` created in the price pane and
positioned via `timeToCoordinate`. Task 1's `.read` block + CSS is consumed by Task 2's unchanged panel
structure (Task 2 only changes the window, not the row markup). ✓
