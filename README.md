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

# Deep fundamentals: valuation (P/E, forward P/E, PEG), growth, margins, debt, FCF.
./.venv/bin/python tools/fundamentals.py NVDA
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
- **Phase 6:** proactive watchdog — scheduled portfolio check-ins (big moves, overbought/oversold, predictions due).
