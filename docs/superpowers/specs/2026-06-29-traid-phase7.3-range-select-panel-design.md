# TRaid Phase 7.3 — Range Selection + Panel Layout Fix (design)

> Status: approved 2026-06-29. Builds on Phase 7 / 7.1 / 7.2. Decision-support, not financial advice.

## Goal

1. **Fix the condensed info panel** — the fundamentals rows currently overflow (label + value +
   the full classifier reading crammed into one ~230px row, the reading wrapping over the value).
   Restructure so each metric reads cleanly with room to breathe.
2. **Drag-to-select a period.** Hold **Shift** and click-drag across the price chart to select a
   range of candles. While a selection is active: the info panel + fundamentals + all stats
   reflect the **selected** candle range (not the full visible range); the selected candles stay
   full opacity and **everything outside the selection dims to ~40%**. A plain click (no Shift)
   clears the selection and returns to visible-range summary.

## Non-goals (YAGNI)

- No persisted selections, no multi-select, no draggable handles to resize a selection (re-drag to redo).
- No per-candle recolor for the dim — use overlay masks (simpler, robust).

## Panel layout fix

- **Fundamentals rows:** render each as a label+value line, with the classifier **reading on its own
  full-width muted line below** (wraps naturally, no overlap). Strip the redundant leading "P/E 29.48 — "
  from the reading where the value is already shown (show just the descriptive tail, e.g. "elevated
  (priced for growth)"), or show label+value then the reading beneath — pick the cleaner; no value
  should appear twice on one line.
- **General:** add a little vertical rhythm (row spacing / line-height), keep section separators.
  Long readings never share a line with a value. The indicator rows (short tags like "Neutral") can
  stay as label · value · tag.
- Keep the `data-tip` tooltips intact on all labels.

## Range selection

State: `sel = {from, to}` (times) or `null`.

- **Start:** `mousedown` on the price chart container with `e.shiftKey` → record start x →
  `price.timeScale().coordinateToTime(x)` (and logical index). Prevent the chart's own drag-scroll
  while Shift is held.
- **Drag:** `mousemove` → live-update the selection (masks + optional thin selection border).
- **End:** `mouseup` → finalize `sel` as the ordered [from,to]; recompute the panel over the selected
  candles; keep masks drawn.
- **Clear:** `mousedown` without Shift (a normal click/drag) → `sel = null`, hide masks, panel reverts
  to visible-range summary.
- **Dim masks:** two absolutely-positioned divs over the price pane — left mask (pane-left → selection
  start x) and right mask (selection end x → pane-right), `background: rgba(14,14,18,0.6)`
  (the page bg at ~60% → the candles beneath read at ~40%), `pointer-events:none`, `z-index` above the
  canvas but below the toggle chips. Reposition on every `subscribeVisibleLogicalRangeChange` and on
  resize via `timeScale().timeToCoordinate(sel.from/sel.to)` (hide a mask if its edge is off-screen /
  clamp to pane bounds). Masks only on the PRICE pane (the visual anchor); sub-panes need not dim.
- **Panel when selection active:** header shows "SELECTION" and the date range; O/H/L/C/change/high/low/
  %-from-high/vol-avg/ATR/%B/S-R-distance all computed over the selected candles; indicator values use
  the last defined value within the selection; fundamentals block unchanged (it's ticker-level). Hover
  still overrides to a single candle while hovering.

## Render notes

- All in `tools/chart_render.py`. The masks + selection handlers are wired once at top level (not in
  `loadResolution`). On resolution switch, clear any active selection (candle times differ per
  resolution) and hide masks.
- Reuse the existing summary computation, parameterized by a [loIdx, hiIdx] window: visible-range when
  no selection, selected window when `sel` set.

## Testing

- **Render (pure string):** output contains the selection mask elements (e.g. `id="mask-left"`/
  `id="mask-right"` or a `.dim-mask` class), a `shiftKey` guard, `coordinateToTime`, and the
  restructured fundamentals markup (reading on its own line — e.g. a `.read` block, not inline with the
  value). Embedded `const DATA = …;` still round-trips.
- **Browser** (Shift-drag selects + dims outside, panel reflects selection, click clears, masks track
  pan/zoom, resolution switch clears selection) verified manually.

## Open follow-ups (not this phase)

- Resizable selection handles; keyboard nudge; persist selection across reloads.
