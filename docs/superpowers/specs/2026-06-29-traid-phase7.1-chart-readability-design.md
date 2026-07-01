# TRaid Phase 7.1 — Chart Readability & Multi-Resolution (design)

> Status: approved 2026-06-29. Builds on Phase 7 (interactive charts). Decision-support, not financial advice.

## Goal

Make the interactive chart genuinely comparable and readable, and let Martin switch the
candle timeframe live. Five things, on the same `feat/phase7-interactive-charts` branch:

1. **Fix x-axis linking (the bug).** Panes drift out of horizontal alignment when zooming
   *out* (see Phase 7.1 screenshots): the time-based sync clamps because each indicator
   series starts at a different date (warm-up bars were dropped). Fix at the data layer so
   all panes share an identical time domain, then sync by logical (index) range.
2. **Vertical alignment.** Pin every pane to the same price-axis width and hide the
   redundant middle time-axes, so a given date sits at the same x-position in all panes
   (only the bottom pane shows the time axis, TradingView-style).
3. **Linked crosshair.** Hovering any pane draws a vertical guide + value markers at that
   same date on all four panes.
4. **Right-side info panel.** A fixed sidebar that by default summarizes the *currently
   visible range*, and on hover shows the *single hovered candle's* values — both with
   plain-English readings.
5. **In-chart timeframe selector.** Buttons **1h · 1d · 1w · 1m**; each resolution's
   candles + indicators are computed in Python and embedded, and a click swaps them live.

## Non-goals (YAGNI)

- No server/live-refresh; charts remain self-contained snapshots generated on demand.
- No drawing tools, no saved annotations.
- No resolutions beyond 1h/1d/1wk/1mo. (1h is capped to yfinance's intraday window.)

## Root-cause of the sync bug

`chart_data._line` *dropped* NaN warm-up points, so e.g. candles had 251 points but RSI
had 237 — different lengths and different start dates. Logical-range sync (index i) and
time-range sync both then map "the same window" to different dates per pane. **Fix:** emit
an invisible *whitespace* point (`{"time": d}`, no `value`) for warm-up bars instead of
dropping them. Every series then has identical length and dates → index i is the same date
in every pane → logical-range sync is exact in both zoom directions.

## Data layer

### Whitespace padding (fixes 1)
`_line` returns one point per bar: `{"time", "value"}` where the indicator is defined,
`{"time"}` (whitespace) during warm-up. lightweight-charts renders whitespace as a gap.

### Multi-resolution payload (feature 5)
- Extend `tools.market.history` with an `interval` parameter (passes yfinance `interval=`).
- New `build_chart_payload(ticker, market=None, period=None)` returns:
  ```
  {
    "ticker", "as_of", "price", "default": "1d",
    "resolutions": {
      "1h":  <series_from_bars output for hourly>,
      "1d":  <... daily ...>,
      "1wk": <... weekly ...>,
      "1mo": <... monthly ...>,
    }
  }
  ```
  Each resolution is the existing `series_from_bars` dict (now whitespace-padded).
- Per-resolution lookback (yfinance constraints; intraday is limited to ~730d):
  `1h → 3mo`, `1d → 1y`, `1wk → 5y`, `1mo → max`. A resolution that yfinance can't
  return (e.g. delisted/no intraday) is omitted from `resolutions` rather than failing the
  whole payload; `default` falls back to the first present resolution.
- `as_of`/`price` come from the daily resolution (or the default if daily absent).

## Render layer (self-contained HTML, lightweight-charts@4.1.3)

`render_chart_html(payload, meta=None)` is rewritten to consume the payload:

- **Panes** unchanged in content (price+BB+volume, RSI, MACD, stochastic) but:
  - all four share `rightPriceScale.minimumWidth` (fixed, e.g. 72px) → vertical alignment;
  - time axis visible only on the bottom (stochastic) pane;
  - sync via `subscribeVisibleLogicalRangeChange` / `setVisibleLogicalRange` (exact now
    that domains match), `fitContent()` on all.
- **Linked crosshair:** `subscribeCrosshairMove` on each pane → `setCrosshairPosition`
  on the others at the same time (using each pane's primary series + its value at that
  time, looked up from an index built once per resolution).
- **Info panel:** a right sidebar `<div>`.
  - *Summary mode* (no hover): on `subscribeVisibleLogicalRangeChange`, compute over the
    visible candles — date range, O(first)/H(max)/L(min)/C(last), % change, latest defined
    indicator values at the right edge — each with a reading.
  - *Hover mode*: on `subscribeCrosshairMove` with a valid time, show that candle's
    O/H/L/C/Vol and each indicator value at that date, with readings.
  - Readings replicate Phase 7's thresholds in small JS helpers (RSI 70/30, stoch 80/20,
    MACD histogram sign, price vs Bollinger band). Plus static S/R and the TRaid call.
- **Timeframe selector:** a top button row `1h · 1d · 1w · 1m` (only buttons for present
  resolutions). `loadResolution(res)` re-`setData`s every series from
  `payload.resolutions[res]`, redraws S/R price lines, rebuilds the crosshair-value index,
  `fitContent()`s, and refreshes the panel. Active button highlighted. Initial =
  `payload.default`.

## CLI

`chart.py` switches to `build_chart_payload`; `generate_chart`/`write_chart` pass the
payload through to `render_chart_html`. `--period` still overrides the daily lookback;
`--call/--confidence/--call-date` (Phase 7 fix wave) still annotate the title. The session
snapshot/live paths are unchanged.

## Testing

- **Data (no network):** `_line` emits whitespace for warm-up and a value otherwise (every
  series length == bar count); `build_chart_payload` (monkeypatched `history` per interval)
  returns the `resolutions`/`default` shape, omits a resolution whose `history` errors, and
  derives `as_of`/`price` correctly.
- **Render (pure string):** output embeds the payload, contains the resolution toggle
  buttons for present resolutions, the info-panel container, the crosshair-sync and
  logical-sync code, and `minimumWidth`. The embedded `const DATA = …;` JSON round-trips.
- **CLI (no network):** `write_chart` writes the payload-based page; snapshot path/title
  unchanged (existing tests adjusted to the payload shape).
- **Browser interactivity** (zoom-both-ways alignment, crosshair link, panel summary/hover,
  timeframe swap) is verified manually by generating a live chart.

## Open follow-ups (not this phase)

- Per-resolution period overrides from the CLI.
- Tie snapshot generation into the ledger `log` flow (carried over from Phase 7).
