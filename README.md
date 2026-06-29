# TRaid

A personal, risk-first investment analyst that lives inside Claude Code. It knows your
portfolio, fetches free live market data (US + NZX), gives sized and explained
suggestions, and logs every call to a self-verifying ledger. Claude is the brain.

> Personal decision-support tool — **not licensed financial advice.**

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

# Your personal data files are gitignored — create them from the examples:
cp data/portfolio.example.json data/portfolio.json
cp data/profile.example.md     data/profile.md
cp data/notebook.example.md    data/notebook.md
touch data/predictions.jsonl
```

## Use

Open this project in Claude Code and just talk to it:

> "Here's my situation — I've got $200 to put in today. What should I do?"

The `traid-analyst` skill loads your portfolio, pulls live data, reasons, suggests, and logs.

## Your data (gitignored — local only, never pushed)

- `data/portfolio.json` — holdings, cash, risk tolerance
- `data/profile.md` — your goals, horizon, constraints
- `data/notebook.md` — running theses & lessons
- `data/predictions.jsonl` — the append-only call ledger

## Tools (Claude runs these; you can too)

```bash
./.venv/bin/python tools/market.py quote AAPL
./.venv/bin/python tools/market.py quote AIR --market NZX
./.venv/bin/python tools/market.py fx NZDUSD
./.venv/bin/python tools/ledger.py list --limit 10

# Technical indicators (RSI, MACD, Bollinger, 50/200 MA, stochastic, ATR, volume)
# with plain-English readings + a confluence tally. Context for timing — not a trigger.
./.venv/bin/python tools/indicators.py NVDA
./.venv/bin/python tools/indicators.py USF --market NZX --period 2y

# Self-verifying scorecard: grades matured calls, calibrates confidence,
# shows interim marks for open calls. Honest about small samples.
./.venv/bin/python tools/scorecard.py --summary

# Candlestick patterns (0-100 match score) + support/resistance + swing-trend.
# Low-weight context only — patterns have weak, contested predictive power.
./.venv/bin/python tools/patterns.py NVDA

# Interactive chart: zoomable/pannable candles + Bollinger/volume with
# RSI/MACD/stochastic sub-panes. Self-contained HTML (TradingView lightweight-charts).
# Linked panes (x-axis zoom/pan sync), synced crosshair across all 4 panes, right panel
# showing visible-range summary (or hovered candle), and 1H/1D/1W/1M timeframe toggle buttons.
# Per-graph indicator toggles (BB/Vol chips, collapse chips for RSI/MACD/Stochastic),
# richer side panel with fundamentals snapshot (P/E, PEG, margin, growth) plus volatility/range stats,
# and educational hover-tooltips on each metric. Shift+drag the price chart to select a period 
# (dims the rest; the side panel recomputes for that range; click to clear). Live re-pull, or a frozen per-call snapshot. Charts are gitignored (local only).
./.venv/bin/python tools/chart.py NVDA
./.venv/bin/python tools/chart.py AIR --market NZX --period 2y
./.venv/bin/python tools/chart.py META --snapshot --call-id 2026-06-28-001

# Deep fundamentals: valuation (P/E, forward P/E, PEG), growth, margins, debt, FCF.
./.venv/bin/python tools/fundamentals.py NVDA

# Proactive watchdog: checks holdings/predictions and pushes alerts (iPhone + Mac).
./.venv/bin/python tools/watchdog.py --check --dry-run   # preview, nothing sent
```

## Proactive Watchdog (Phase 6) — alerts to your iPhone + Mac

Runs on a schedule and pings you about: a holding moving ≥7% in a day, a
prediction maturing, or your foreign-share cost nearing the NZ$50k FIF line.
Quiet otherwise; never re-nags.

**One-time Telegram setup (free, private):**
1. In Telegram, message **@BotFather** → `/newbot` → follow prompts → copy the **bot token**.
2. `cp .env.example .env` and paste the token into `TELEGRAM_BOT_TOKEN`.
3. Send your new bot any message in Telegram, then:
   `./.venv/bin/python tools/watchdog.py --get-chat-id` → paste the number into `TELEGRAM_CHAT_ID`.
4. Test: `./.venv/bin/python tools/watchdog.py --test` (should buzz your phone + Mac).

**Schedule it (weekdays 9am NZT):**
```bash
cp scripts/com.traid.watchdog.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.traid.watchdog.plist
```

## Syncing holdings from Sharesies (read-only, no credentials)

Sharesies has no official API, but you can export your data safely:

1. In Sharesies: **Manage → Download reports → Transaction report (CSV)**, pick the full date range, export.
2. Save the file into the project (e.g. `data/sharesies.csv` — it's gitignored).
3. Preview, then write it into your portfolio (with **real cost basis**):

```bash
./.venv/bin/python tools/import_sharesies.py data/sharesies.csv          # dry run
./.venv/bin/python tools/import_sharesies.py data/sharesies.csv --write  # update portfolio.json
```

The parser fuzzy-matches column names; if it can't find one it prints your CSV's
headers so the mapping can be adjusted. Your cash balance and risk setting are preserved.

## Tests

```bash
./.venv/bin/pytest -v
```

## Roadmap

- **Phase 1 ✅** conversation-first analyst: live data, portfolio memory, prediction ledger.
- **Phase 2 ✅** technical indicators (RSI/MACD/Bollinger/MA/stochastic/ATR/volume) as confluence.
- **Phase 3 ✅** self-verifying scorecard: auto-grades matured calls, calibrates confidence, honest about small samples.
- **Phase 4 ✅** candlestick pattern recognition (0–100 match scores) + support/resistance/swing structure, as low-weight context.
- **Phase 5 ✅** deep fundamentals — valuation (P/E, forward P/E, PEG), growth, margins/ROE, debt, free cash flow.
- **Phase 6 ✅** proactive watchdog — scheduled alerts to iPhone (Telegram) + Mac for big moves, matured predictions, and the FIF threshold.
