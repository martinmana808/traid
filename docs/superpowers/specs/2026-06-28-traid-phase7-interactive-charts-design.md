# TRaid Phase 7 — Interactive Charts (design)

> Status: approved 2026-06-28. Decision-support tool, not financial advice.

## Goal

Give Martin an interactive, TradingView-style chart for any ticker TRaid discusses —
real candlesticks he can **zoom, pan, and crosshair** — so he can *see* the technical
picture behind a recommendation and then **ask TRaid the "whys and whats" to learn**.

The chart is a shared visual reference; the teaching stays in the Claude Code
conversation (and Telegram). The interactivity Martin wants is two kinds:
chart-UI (zoom/pan) **and** conversational (asking TRaid).

## Non-goals (YAGNI)

- No hosted/phone dashboard yet (possible future "Phase C").
- No live auto-refreshing/streaming prices (re-run to refresh).
- No drawing tools or saved annotations.
- No multi-ticker overlay on a single pane (one chart per ticker; an index page links them).

## User-facing behaviour

- `chart.py META` → pulls **fresh** data, writes `charts/live/META-<date>.html`, opens it in the browser.
- When TRaid makes a recommendation → a **frozen snapshot** is saved per call:
  `charts/sessions/<YYYY-MM-DD>/<TICKER>-<callid>.html`, with data baked in so it
  reopens identically forever, offline. (This is Martin's "both" — snapshot + re-pull.)
- Each session folder gets an `index.html` listing that session's tickers/calls → click through.
  This is the "all these stocks, per session, per purchase" view.
- In chat: "chart META" → TRaid runs the tool, the browser opens, they discuss.

## Architecture & data flow

New CLI tool `tools/chart.py`, following the existing tool pattern:

```
chart.py <TICKER> [--market NZX] [--period 1y] [--snapshot --call-id <id>]
   ├─ fetch OHLC history          (reuse market.py data layer)
   ├─ compute indicators          (reuse indicators.py + patterns.py)
   ├─ build self-contained HTML    (data embedded as JSON; lightweight-charts from CDN)
   └─ save to charts/ and open in browser (webbrowser.open)
```

**Required refactor (targeted, serves this goal):** `indicators.py` and `patterns.py`
currently compute inside their CLI `main()` and only *print* JSON. Extract the
computation into importable functions (e.g. `compute_indicators(df)`,
`compute_structure(df)`) so `chart.py` imports them directly rather than shelling out.
The existing CLI commands keep identical output (they call the new functions and print).

**Dependencies:** none added. lightweight-charts is a CDN `<script>`. Keep yfinance / pandas / numpy.

## The chart (TradingView lightweight-charts)

Dark theme, time-synced panes, native zoom (scroll) / pan (drag) / crosshair readouts.

- **Main pane:** candlesticks + Bollinger upper/middle/lower overlay + volume.
- **Sub-pane — RSI:** line with 30/70 guide lines.
- **Sub-pane — MACD:** MACD line, signal line, histogram.
- **Sub-pane — Stochastic:** %K / %D with 20/80 guides.
- **Overlays:** horizontal lines for nearest support / resistance (from `patterns.py`);
  entry / tranche level markers when a chart is tied to a call.
- **Title bar:** ticker, last price, and — when linked to a recommendation —
  TRaid's call + confidence + date.
- **Legend:** a small "what am I looking at" panel explaining each sub-pane, so Martin
  can self-serve the basics (learning aid).

## Storage & organisation

- `charts/live/<TICKER>-<date>.html` — latest re-pull.
- `charts/sessions/<date>/<TICKER>-<callid>.html` — frozen snapshot per call.
- `charts/sessions/<date>/index.html` — session index linking that session's charts.
- `charts/` is gitignored (personal, like `data/`).

## Components (clear boundaries)

1. **data builder** — given a ticker + period, returns a plain dict of series ready for
   the chart (candles, volume, bollinger, rsi, macd, stochastic, support/resistance).
   Pure-ish; unit-testable from OHLC fixtures.
2. **html renderer** — given that dict + metadata (title, call info), returns a
   self-contained HTML string (template + embedded JSON + CDN script). No network.
3. **cli / orchestration** (`chart.py`) — parse args, call builder + renderer, write
   file(s), open browser, write/update session index.

## Testing

- Unit (pytest, matching `tests/`): data builder produces correct series shapes/values
  from known OHLC fixtures; html renderer embeds the data and references the expected series.
- Smoke: `chart.py <T>` writes a valid, self-contained HTML file (data present, no missing refs).
- Browser interactivity (zoom/pan) is verified manually.

## Open follow-ups (not this phase)

- Tie snapshot generation into the ledger `log` flow so every concrete call auto-produces a chart.
- Possible Phase C: host the snapshots / link from the Telegram bot for phone viewing.
