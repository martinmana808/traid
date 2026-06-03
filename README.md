# TRaid

A personal, risk-first investment analyst that lives inside Claude Code. It knows your
portfolio, fetches free live market data (US + NZX), gives sized and explained
suggestions, and logs every call to a self-verifying ledger. Claude is the brain.

> Personal decision-support tool — **not licensed financial advice.**

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## Use

Open this project in Claude Code and just talk to it:

> "Here's my situation — I've got $200 to put in today. What should I do?"

The `traid-analyst` skill loads your portfolio, pulls live data, reasons, suggests, and logs.

## Your data (edit freely)

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
```

## Tests

```bash
./.venv/bin/pytest -v
```

## Roadmap

- **Phase 2:** technical indicators (RSI/MACD/Bollinger) + richer fundamentals.
- **Phase 3:** auto-verify matured predictions + self-calibrating scorecard.
