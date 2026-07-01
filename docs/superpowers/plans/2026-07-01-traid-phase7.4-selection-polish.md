# Phase 7.4 — Selection Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Checkbox steps.

**Goal:** Make Shift+drag range selection cohesive across all panes: dim/slice RSI/MACD/Stochastic too, lock the right panel and hover strictly to the selected area, and add an (X) button to clear the selection.

**Architecture:** All in `tools/chart_render.py`. Extend the existing `sel`/`positionMasks`/crosshair/`updateSummaryPanel` machinery from Phase 7.3.

## Global Constraints
- No new Python deps; lightweight-charts v4; pure render; `const DATA = __DATA__;\n` intact.
- Don't break: timeframe toggle, per-graph collapse toggles, pane sync, tooltips, Task-7.3 selection basics.
- Panes are x-aligned (equal `minimumWidth`, synced logical range) → a given time maps to the same x across panes, so mask x-coords computed once from the price timeScale apply to every pane.

---

### Task 1: Extend selection to all panes + hover restriction + clear button

**Files:** Modify `tools/chart_render.py`; Test `tests/test_chart_render.py`.

**Requirements:**

1. **Dim masks on ALL four panes.** Today only `#price` has `#mask-left`/`#mask-right`. Add a left+right `.dim-mask` pair inside each of `#rsi`, `#macd`, `#stoch` too (so 8 mask divs total). Give them ids like `mask-left-price/right-price/left-rsi/right-rsi/left-macd/right-macd/left-stoch/right-stoch` (or keep a per-pane lookup). Refactor `positionMasks()` to compute `fromX`/`toX` once (via `price.timeScale().timeToCoordinate(sel.from/to)`, clamped to [0, price plot width]) and apply those x-spans to the left/right masks of EVERY pane (each mask spans its own pane's full height via `top:0;bottom:0`). `hideMasks()` hides all 8. Collapsed panes: their masks are inside a 0-height pane, so they're harmless; no special-casing needed, but skip positioning a pane whose element is `.collapsed` if convenient.

2. **Right panel reflects ONLY the selection** (already true when `sel` set — keep it; verify the windowed `updateSummaryPanel` uses the selected candle indices and the "Selection <from>→<to>" header).

3. **Restrict hover to inside the selection.** In the crosshair `subscribeCrosshairMove` handler: when `sel` is active and `param.time` is OUTSIDE `[sel.from, sel.to]`, do NOT call `showHoverPanel` — instead keep the selection summary (call `updateSummaryPanel()` / leave it) and do not show a per-candle readout. When `param.time` is inside the selection → `showHoverPanel(param.time)` as today. When `sel` is null → hover works everywhere (unchanged). (The linked crosshair line may still draw natively; this requirement is about the panel info + not reacting to out-of-selection hovers.)

4. **(X) clear button.** Add a floating button `<div id="sel-clear">×</div>` inside `#price` (CSS: `position:absolute;z-index:6;cursor:pointer;pointer-events:auto;display:none;` small dark rounded chip with an ×). Show it only when `sel` is active; position it at the top-right of the selection band — near `toX`, `top:4px` — inside `positionMasks()`. Clicking it calls `clearSelection()` (and `e.stopPropagation()` so it doesn't trigger the pane's mousedown-clear/pan). `clearSelection()` hides it (via `hideMasks()` or explicitly).

**Implementation guidance:** keep all handlers wired once. `positionMasks()` now also positions/show-hides `#sel-clear`. `clearSelection()` hides all masks + the button. The hover-restriction is a 3-line guard in the crosshair handler using `sel.from`/`sel.to` bounds (times are comparable — numbers for intraday, ISO strings sort correctly for daily; use the candle index comparison if safer: find hovered index and check it's within the selected [loIdx,hiIdx]).

- [ ] **Step 1: Failing test** — add to `tests/test_chart_render.py`:

```python
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
```

- [ ] **Step 2: Run → fail.** `./.venv/bin/python -m pytest tests/test_chart_render.py::test_selection_spans_all_panes_and_has_clear_button -v`

- [ ] **Step 3: Implement** the per-pane masks, `positionMasks` refactor (compute x once, apply to all panes + position `#sel-clear`), the crosshair hover-restriction guard, and the clear button + its click handler. Keep Phase 7.3 behavior otherwise.

- [ ] **Step 4: Run → pass, then full suite** `./.venv/bin/python -m pytest -q`.

- [ ] **Step 5: Manual smoke (network):** `./.venv/bin/python tools/chart.py NVDA` — confirm: Shift+drag dims ALL four panes to the same slice; the right panel shows only the selected range; hovering inside the selection shows that candle, hovering outside does nothing; the (X) clears it; masks + button stay aligned on pan/zoom; switching timeframe clears it. (Headless: `grep -c dim-mask` ≥ 8, `id="sel-clear"` present.)

- [ ] **Step 6: Commit.** `git add tools/chart_render.py tests/test_chart_render.py && git commit -m "feat: selection dims all panes, panel/hover locked to selection, add clear (X) button"`

---

### Task 2: Docs

**Files:** Modify `README.md`, `.claude/skills/traid-analyst/SKILL.md`.

- [ ] **Step 1:** Update the chart notes: Shift+drag now dims all panes to the slice, the panel + hover are limited to the selection, and an (X) clears it.
- [ ] **Step 2:** SKILL.md chart bullet: same one-line note.
- [ ] **Step 3: Commit.** `git add README.md .claude/skills/traid-analyst/SKILL.md && git commit -m "docs: note Phase 7.4 selection polish"`

---

## Self-Review
Spec coverage: all-pane masks → Task 1 R1; panel-only-selection → R2 (existing, verified); hover restricted to selection → R3; (X) clear → R4; docs → Task 2. Placeholder scan: concrete requirements + structural test; browser behavior manually verified (Task 1 Step 5). Type consistency: `positionMasks`/`hideMasks`/`clearSelection` extended to 8 masks + `#sel-clear`; crosshair guard uses `sel.from`/`sel.to` (or selected index window) consistent with `updateSummaryPanel`'s windowing.
