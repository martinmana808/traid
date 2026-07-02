# TRaid Autopilot (paper) — design

> Status: APPROVED-PENDING-SPEC-REVIEW — brainstormed & agreed 2026-07-02.
> Decision-support experiment, **NOT licensed financial advice.** Paper money only.

## One line
A fully **local**, self-running paper-trading bot. **Fable 5** makes buy/sell/hold
calls **3× per US market day** on Martin's watchlist; hard risk rails are enforced in
**Python**; Martin just opens a plain **text file** to see how it's doing. No broker
account, no cloud, no approval step.

## Goal & philosophy
Let Fable invest a simulated **$5,000** on the watchlist, hands-off, and honestly
report how it does versus simply holding. It's an experiment: if the results are good
over time, *then* Martin might consider a small real-money slice later. Until then it's
Monopoly money in a JSON file — which also sidesteps any NZ "trader" tax question
entirely (no real trades occur).

## Agreed decisions
- **Brain:** Fable 5, run as a **subagent** spawned by a **headless Claude Code** run
  (`claude -p …`). This keeps it on Martin's Claude subscription — **no separate API
  bill** — while still being genuinely Fable.
- **Capital:** $5,000 simulated. **Universe:** `watchlist.json` (~38 names) as a hard
  whitelist — the bot cannot touch anything else.
- **Cadence:** 3×/day, weekdays, at fixed Argentina times chosen to stay inside US
  market hours in **both** EDT and EST:
  - **12:00 ART** — morning read
  - **14:15 ART** — midday check
  - **16:30 ART** — last call before the US close
- **Autonomy:** fully autonomous — **no approval step.** It just trades and writes the file.
- **Trading style:** **long-only** (no shorting) and **day trading allowed** (it may buy
  and sell the same name the same day across the three runs).
- **Sizing:** Fable sizes within hard rails. **Rails enforced in code, not the prompt.**
- **Broker:** **none** — a local Python paper broker. Fills happen at the live yfinance
  price. No Alpaca, no keys, no external account.
- **Delivery:** everything local. **No Telegram, no Vercel, no GitHub push.** Output is a
  single plain-text status file Martin opens whenever he wants.

## Deliberate simplifications from the earlier draft (YAGNI)
Dropped, on purpose, to match "local, cheap, just a text file":
- **Alpaca** → replaced by a local Python paper broker (a JSON account file).
- **Telegram approval loop** → removed; the bot is fully autonomous.
- **Dedicated second Telegram bot / Anthropic API key** → not needed (Fable runs as a
  free subagent under the subscription).

## Components (each small, one job, testable)
- **`data/autopilot/account.json`** — the paper broker state: `starting_capital`, `cash`,
  `positions` (`[{ticker, shares, avg_cost}]`), `created_at`, `halted` flag.
- **`data/autopilot/trades.jsonl`** — append-only fill log: timestamp, side, ticker,
  shares, price, and Fable's one-line reason.
- **`data/autopilot/status.txt`** — the human-readable file Martin checks (see format below).
- **`tools/autopilot_broker.py`** — pure paper-broker logic: mark-to-market, apply a
  fill, compute cash/positions/P&L. No I/O beyond the account file. Heavily unit-tested.
- **`tools/autopilot_rails.py`** — pure validator; the safety core (see rails below).
- **`tools/autopilot.py`** — the runner CLI with two verbs so all money-logic is in
  Python and testable:
  - `prepare` → prints JSON: market-open status, current account marked-to-market, and a
    compact per-ticker snapshot of the watchlist (reusing `market`/`indicators`/
    `fundamentals`).
  - `execute '<orders-json>'` → runs each proposed order through the rails, fills the
    survivors via the broker, appends to `trades.jsonl`, rewrites `status.txt`, prints a
    summary. Rejected orders are logged, never filled.
- **`scripts/com.traid.autopilot-{morning,midday,close}.plist`** — three launchd jobs
  (same pattern as the existing watchdog), each wrapping the run in `caffeinate` so a
  sleeping Mac wakes for it.

## Data flow (one run)
```
launchd (12:00 / 14:15 / 16:30 ART, weekdays)
  └─ caffeinate → claude -p "run the TRaid autopilot"    (headless, subscription)
       1. python tools/autopilot.py prepare        → market-open check + snapshot JSON
       2. spawn Fable subagent(snapshot)            → proposed orders + one-line reasons
       3. python tools/autopilot.py execute '<...>' → rails → fills → status.txt
       4. exit
```
If the market is closed (weekend / holiday / DST edge), step 1 reports it and the run
just refreshes `status.txt` without trading. Fable only ever produces a *proposal*;
Python decides what is legal and what actually fills.

## The rails (hard limits, enforced in `autopilot_rails.py`)
- **Long-only** — reject any sell of shares not held; no shorting.
- **No leverage** — reject buys that exceed available cash.
- **Watchlist-only** — reject any ticker not in `watchlist.json`.
- **Max 40% per name** — reject a buy that would push one position past 40% of total
  account value.
- **Circuit breaker at −25%** — if total account value is ≤ 25% below the $5,000 start,
  set `halted` and allow **no new buys** (hold/sell only); `status.txt` states it clearly.
- **Market-open guard** — no fills when the US market is closed.
Every rejected order is written to the log with its reason; it never touches the account.

## `status.txt` format (rewritten every run)
```
TRaid Autopilot — paper
Updated: 2026-07-02 16:30 ART   (next run: 2026-07-03 12:00 ART)

BALANCE   $5,214.30    ▲ +$214.30  (+4.29%)   since $5,000 start
CASH      $1,020.11    INVESTED $4,194.19

POSITIONS
  NVDA   12 sh  @ $118.40 avg   now $131.02   ▲ +10.7%   $1,572
  META    3 sh  @ $702.10 avg   now $698.40   ▼  -0.5%   $2,095

LAST MOVES
  16:30  BUY  2 NVDA @ $131.02  — "momentum + RSI still <70"
  14:15  HOLD everything        — "no edge, spreads tight"
```
Shows balance, the % and $ above/below the start, current positions with per-name P&L,
and what it did (and why) — exactly what Martin asked to be able to check.

## Error handling / guardrails
Rails in code; market-closed → status-only, no trades; halt-on-drawdown; a missing/failed
Fable proposal → skip the run's trades but still refresh status; each run is idempotent
(re-running the same slot won't double-fill because fills are driven by the fresh
proposal, and the account file is the single source of truth).

## Testing
Pure Python core is unit-tested and offline (Fable mocked):
- broker: fill math, avg-cost update, mark-to-market, cash/P&L correctness;
- rails: over-40% buy rejected, leverage rejected, off-watchlist rejected, short
  rejected, circuit breaker trips at −25% and blocks buys;
- runner: `prepare` output shape and `execute` end-to-end with a mocked orders payload.
Manual smoke test of one real headless run before letting the schedule take over.

## What Martin must provide
Essentially nothing new: no API keys, no accounts. Just approve, then let the build wire
up the launchd jobs. His Mac needs to be awake at the three ART times (`caffeinate`
handles brief sleep at the firing minute).

## Open items to confirm at spec review
- Watchlist file path/shape check (`watchlist.json` at project root).
- Whether Fable is selectable as a subagent model in this environment; if not, fall back
  to Opus for the brain (design is otherwise identical) — flag to Martin before build.
- Exact per-run snapshot size (how many indicators per ticker) to keep the Fable prompt lean.
