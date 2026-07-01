# TRaid Phase 7.2 — Indicator Toggles, Richer Panel, Educational Tooltips (design)

> Status: approved 2026-06-29. Builds on Phase 7 / 7.1. Decision-support, not financial advice.

## Goal

Three chart upgrades, same `feat/phase7-interactive-charts` branch:

1. **Per-graph indicator toggles.** Chips at the top-left of each graph to show/hide indicators.
   - On the **price** graph: `BB` (Bollinger) and `Vol` (Volume) chips toggle those overlays.
   - On each **sub-graph** (RSI / MACD / Stochastic): a chip that **collapses** that pane when
     off (the remaining panes grow to reclaim the space); the thin label/chip row stays so it
     can be re-enabled. Collapsed panes are excluded from axis sync and the crosshair.
2. **Richer right panel.** Add derived stats (all from already-loaded data) plus a fundamentals
   block (P/E, forward P/E, PEG, margin, growth) fetched at generation.
3. **Educational tooltips.** Hovering any label in the right panel shows a rich styled tooltip
   explaining that metric — directly serving the "learn while you look" goal.

## Non-goals (YAGNI)

- No saved layout/preferences (toggles reset on reload).
- No new indicators beyond what's already computed (+ ATR, added for the panel).
- No live fundamentals refresh; fundamentals are a generation-time snapshot.

## Data layer

- **ATR series** — `series_from_bars` gains an `atr` line series (reuse `tools.indicators.atr`,
  whitespace-padded like the others) so the panel can show volatility.
- **Fundamentals snapshot** — `build_chart_payload` calls `tools.fundamentals.analyze(ticker, market)`
  once and embeds the result as `payload["fundamentals"]` (the `{valuation, growth, profitability,
  health, name, sector, summary}` dict), or `None` if it errors (never fatal to the chart).

## Render layer (chart_render.py)

### Per-graph toggles
- A small absolutely-positioned chip row at the **top-left of each `.pane`** (or its label row).
- **Price:** `BB`, `Vol` chips → `series.applyOptions({visible:false/true})` on the Bollinger
  trio / volume series. Active chip styled; default both on.
- **Sub-panes:** a chip (e.g. `RSI`) toggles a `collapsed` class on that pane that sets its
  `flex:0; min-height:0; height:0; overflow:hidden` (label row stays). A collapsed pane's chart
  is removed from the `charts` sync array and the crosshair loop while hidden, and re-added when
  shown; on show, the remaining flex re-distributes and `fitContent()` runs. Default all on.

### Richer panel
Add to the existing summary/hover panel (all derived in JS from the current resolution unless noted):
- **Range:** visible-range % change (have it), plus visible high/low and **% below the high**.
- **Volume:** latest vs its trailing average (×).
- **ATR:** latest ATR and **% of price** (volatility).
- **Bollinger %B** at the right edge.
- **Distance to S/R:** % to nearest support and resistance.
- **Fundamentals block** (from `payload.fundamentals`, static): name · sector; P/E, forward P/E,
  **PEG**, profit margin, revenue growth — each with its tag/reading. Omitted if `fundamentals`
  is null. Header notes "snapshot — not live."
- Hover mode still shows the single candle's O/H/L/C/Vol + indicator values.

### Educational tooltips
- Each panel label/metric carries a `data-tip="<key>"`. A single tooltip `<div>` (absolutely
  positioned, dark, ~260px, rich text) shows on `mouseover` of any `[data-tip]` and hides on
  `mouseout`, positioned near the cursor. Explanations come from a JS dictionary `TIPS` covering:
  RSI, MACD, Bollinger / %B, Stochastic, ATR, Volume, Support/Resistance, P/E, Forward P/E, PEG,
  Margin, Revenue growth, Change%, and "% from high". Each tip is 1–3 plain-English sentences,
  honest about what the metric does and doesn't tell you. Ends implicitly within the not-advice framing.

## Testing

- **Data (no network):** `series_from_bars` includes a full-length `atr` series (whitespace warm-up);
  `build_chart_payload` embeds `fundamentals` from a monkeypatched `analyze`, and sets it to `None`
  when `analyze` returns an error — never fatal.
- **Render (pure string):** output contains the per-pane toggle chips (`data-toggle` for bb/vol/rsi/
  macd/stoch), the fundamentals block markers, the extra stat labels, the `TIPS` dictionary, a
  `[data-tip]` attribute, and the tooltip container. Embedded `const DATA = …;` still round-trips.
- **Browser** (toggle hide/collapse, panel richness, tooltip hover) verified manually via a live chart.

## Open follow-ups (not this phase)

- Persist toggle/layout preferences.
- Per-resolution fundamentals is meaningless; keep it a single snapshot.
