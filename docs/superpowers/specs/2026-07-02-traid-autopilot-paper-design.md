# TRaid Autopilot (paper) — design

> Status: APPROVED-PENDING-SPEC-REVIEW — brainstormed & agreed 2026-07-02.
> Decision-support experiment, **NOT licensed financial advice.** Paper money only.

## One line
A fully **local**, self-running paper-trading bot. An AI brain (**Fable 5**, then
**Opus 4.8**) makes buy/sell/hold calls **every hour the US market is open**, over a
**5 trading-day** run, on Martin's watchlist. Hard risk rails are enforced in **Python**;
Martin just opens a plain **text file** to see how it's doing. No broker account, no
cloud, no approval step.

## Goal & philosophy
Let an AI invest a simulated **$5,000** on the watchlist, hands-off, and honestly report
how it does versus simply holding. It's a short experiment (5 days ≈ mostly luck — framed
that way, never as proof). If results are good over time, *then* Martin might consider a
small real-money slice later. Until then it's Monopoly money in a JSON file — which also
sidesteps any NZ "trader" tax question entirely (no real trades occur).

## Agreed decisions
- **Brain (scheduled by date):** run as a **subagent** spawned by a **headless Claude
  Code** run (`claude -p …`), so it stays on Martin's Claude subscription — **no separate
  API bill** — while still being a genuine frontier model:
  - **Mon Jul 6 & Tue Jul 7 → Fable 5** (while it's available, expires Jul 7).
  - **Wed Jul 8, Thu Jul 9, Fri Jul 10 → Opus 4.8.**
  - The runner selects the model purely from the current date; the handoff is invisible.
- **Capital:** $5,000 simulated. **Universe:** `watchlist.json` (~38 names) as a hard
  whitelist — the bot cannot touch anything else.
- **Duration:** 5 trading days, **Mon Jul 6 → Fri Jul 10 2026** (all normal sessions; the
  Jul 3 Independence-Day-observed closure is avoided by starting Monday).
- **Cadence:** **every hour the market is open** (~6–7 runs/session, 9:30am–4:00pm NY).
- **Scheduling:** a **single hourly launchd job** across a wide Argentina window, wrapped
  in `caffeinate`. The bot's own **market-open guard** decides whether a given hour trades
  or just refreshes the status file — so DST and the exact clock never need hand-tuning.
- **Autonomy:** fully autonomous — **no approval step.**
- **Trading style:** **long-only** (no shorting) with **day trading allowed** (it may buy
  and sell the same name the same day across the hourly runs).
- **Sizing:** the brain sizes within hard rails. **Rails enforced in code, not the prompt.**
- **Broker:** **none** — a local Python paper broker; fills at the live yfinance price. No
  Alpaca, no keys, no external account.
- **Delivery:** everything local. **No Telegram, no Vercel, no GitHub push.** Output is a
  single plain-text status file Martin opens whenever he wants.

## Data the brain sees each run ("the good TRaid data" + news)
A compact per-ticker snapshot, reusing existing tools, kept lean so hourly runs stay cheap:
- **Technical** — RSI, MACD, Bollinger, MA50/200, stochastic, ATR, volume, confluence
  (`indicators.py`), plus candlestick patterns + support/resistance (`patterns.py`).
- **Fundamental** — P/E, forward P/E, **PEG**, growth, margins, ROE, debt, FCF, analyst
  rating/target (`fundamentals.py`). **Cached once per day** (fundamentals barely move
  intraday) so only price/technicals/news refresh each hour.
- **News** — top 1–3 recent headlines per ticker via `yfinance`'s free news feed (title,
  source, link), refreshed each run. Honest limits: headlines only, no deep analysis,
  news-sentiment is noisy — a *hint*, weighted like the momentum signals, never a trigger.

## Deliberate simplifications from the earlier draft (YAGNI)
Dropped on purpose to match "local, cheap, just a text file": **Alpaca** (→ local paper
broker), the **Telegram approval loop** (→ fully autonomous), and any **dedicated Telegram
bot / Anthropic API key** (→ brain runs as a free subagent under the subscription).

## Components (each small, one job, testable)
- **`data/autopilot/account.json`** — paper broker state: `starting_capital`, `cash`,
  `positions` (`[{ticker, shares, avg_cost}]`), `created_at`, `halted` flag.
- **`data/autopilot/trades.jsonl`** — append-only fill log: timestamp, side, ticker,
  shares, price, and the brain's one-line reason.
- **`data/autopilot/fundamentals_cache.json`** — daily-refreshed fundamentals per ticker.
- **`data/autopilot/status.txt`** — the human-readable file Martin checks (format below).
- **`tools/autopilot_broker.py`** — pure paper-broker logic: mark-to-market, apply a fill,
  compute cash/positions/P&L. Heavily unit-tested.
- **`tools/autopilot_rails.py`** — pure validator; the safety core (rails below).
- **`tools/autopilot_news.py`** — thin `yfinance` news fetch (top headlines per ticker).
- **`tools/autopilot.py`** — the runner CLI with two verbs so all money-logic is in Python
  and testable:
  - `prepare` → prints JSON: market-open status, **which brain model today**, account
    marked-to-market, and the per-ticker snapshot (technical + cached fundamentals + news).
  - `execute '<orders-json>'` → runs each proposed order through the rails, fills survivors
    via the broker, appends `trades.jsonl`, rewrites `status.txt`, prints a summary.
    Rejected orders are logged, never filled.
- **`scripts/com.traid.autopilot.plist`** — one hourly launchd job (like the watchdog),
  wrapping `claude -p "run the TRaid autopilot"` in `caffeinate`.

## Data flow (one run)
```
launchd (hourly, wide ART window, weekdays)
  └─ caffeinate → claude -p "run the TRaid autopilot"    (headless, subscription)
       1. python tools/autopilot.py prepare        → market-open + today's model + snapshot
       2. spawn subagent(model=today's brain, snapshot) → proposed orders + reasons
       3. python tools/autopilot.py execute '<...>' → rails → fills → status.txt
       4. exit
```
Market closed (weekend / holiday / off-hours) → step 1 says so and the run just refreshes
`status.txt` without trading. The brain only produces a *proposal*; Python decides what is
legal and what actually fills.

## The rails (hard limits, enforced in `autopilot_rails.py`)
- **Long-only** — reject any sell of shares not held; no shorting.
- **No leverage** — reject buys exceeding available cash.
- **Watchlist-only** — reject any ticker not in `watchlist.json`.
- **Max 40% per name** — reject a buy that would push one position past 40% of total value.
- **Circuit breaker at −25%** — if total value is ≤ 25% below the $5,000 start, set
  `halted` and allow **no new buys** (hold/sell only); `status.txt` states it clearly.
- **Market-open guard** — no fills when the US market is closed.
Every rejected order is logged with its reason; it never touches the account.

## `status.txt` format (rewritten every run)
```
TRaid Autopilot — paper       brain today: Fable 5
Updated: 2026-07-06 15:00 ART   (next run: 2026-07-06 16:00 ART)

BALANCE   $5,214.30    ▲ +$214.30  (+4.29%)   since $5,000 start
CASH      $1,020.11    INVESTED $4,194.19

POSITIONS
  NVDA   12 sh  @ $118.40 avg   now $131.02   ▲ +10.7%   $1,572
  META    3 sh  @ $702.10 avg   now $698.40   ▼  -0.5%   $2,095

LAST MOVES
  15:00  BUY  2 NVDA @ $131.02  — "momentum + RSI still <70, upbeat headline"
  14:00  HOLD everything        — "no edge, spreads tight"
```
Shows balance, the % and $ above/below the start, current positions with per-name P&L, and
what it did (and why) — plus which brain is driving today.

## Error handling / guardrails
Rails in code; market-closed → status-only, no trades; halt-on-drawdown; a missing/failed
brain proposal → skip that run's trades but still refresh status; each run is idempotent
(fills are driven by the fresh proposal, and the account file is the single source of
truth); yfinance/news errors on one ticker degrade gracefully (that ticker just carries
less data into the snapshot).

## Testing
Pure Python core is unit-tested and offline (brain + network mocked):
- broker: fill math, avg-cost update, mark-to-market, cash/P&L correctness;
- rails: over-40% buy rejected, leverage rejected, off-watchlist rejected, short rejected,
  circuit breaker trips at −25% and blocks buys;
- model selector: correct brain chosen per date (Fable ≤ Jul 7, Opus after);
- news + fundamentals cache: shape and daily-refresh behaviour (mocked);
- runner: `prepare` output shape and `execute` end-to-end with a mocked orders payload.
Manual smoke test of one real headless run before the schedule takes over.

## What Martin must provide
Essentially nothing new: no API keys, no accounts. Just approve, then let the build wire up
the hourly launchd job. His Mac needs to be awake at run times (`caffeinate` covers brief
sleep at the firing minute).

## Open items to confirm at spec review
- Watchlist file path/shape check (`watchlist.json` at project root).
- Confirm Fable **and** Opus are both selectable as subagent models in this environment;
  if Fable isn't, Mon/Tue simply use Opus too (design otherwise identical) — flag before build.
- Final per-run snapshot size (how many indicators/headlines per ticker) to keep the prompt lean.
