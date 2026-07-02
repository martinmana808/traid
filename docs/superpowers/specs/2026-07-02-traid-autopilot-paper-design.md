# TRaid Autopilot (paper) — design

> Status: DRAFT — design brainstormed 2026-07-02, awaiting Martin's approval before writing the implementation plan.
> Decision-support experiment, NOT licensed financial advice.

## Goal
A scheduled AI agent that, **3× per US market day for 5 days**, reads Martin's watchlist through TRaid's existing tools, asks **Fable 5** for buy/sell/hold proposals (technical + fundamental), sends them to **Telegram for approval**, and places approved orders on an **Alpaca paper** account ($5,000 fake). Fully paper — no real money — because frequent trading risks NZ "trader" tax classification. If results are strong, revisit real money later (small play-money slice via Interactive Brokers, the only realistic API broker for a NZ resident; Sharesies has no API, Alpaca live is US-only).

## Agreed decisions
- **Model:** Fable 5 (Anthropic API). **Capital:** $5,000 paper (Alpaca paper). **Duration:** 5 US market days.
- **Cadence:** 3 check-ins/day — US open, midday, close.
- **Universe:** `watchlist.json` (~38 names) as a hard whitelist — the agent cannot touch anything else.
- **Autonomy:** propose → Martin approves (never auto-executes).
- **Approval channel:** Telegram, via a **dedicated second bot** (Telegram forbids the existing webhook bot + polling on one token).
- **Sizing:** Fable sizes within hard rails — long-only, no leverage, ≤40% per name, auto-halt at −15% drawdown. **Rails enforced in code, not just the prompt.**
- **Analysis inputs:** indicators + patterns (technical), fundamentals + the Phase-7.6 technicals rating (fundamental/derived).

## Flow per check-in
1. Alpaca market clock — if closed (weekend/holiday), no-op.
2. Halt check — if paper equity ≤ −15% from $5k, stop the experiment and notify.
3. Gather per-ticker signals for the watchlist (reuse `market`/`indicators`/`patterns`/`fundamentals`).
4. Ask Fable 5 for structured proposals (buy/sell/hold + size + one-line reasoning).
5. Validate every proposal against the rails in code; clip/drop violations before Martin sees them.
6. Send numbered proposals + reasoning to Telegram; wait a bounded window for `approve 1,3` / `approve all` / `skip`.
7. Place approved orders on Alpaca paper → log to a run ledger → confirm in Telegram.
8. No reply in window → place nothing.

## Components (each small, testable)
- `tools/broker_alpaca.py` — thin Alpaca **paper** REST client (account, positions, place order, clock).
- `tools/agent_signals.py` — assembles the compact per-ticker snapshot for Fable (reuses existing tools).
- `tools/agent_decide.py` — builds the prompt, calls Fable 5, parses structured proposals.
- `tools/agent_rails.py` — pure hard-limit validator (safety core; heavily unit-tested).
- `tools/trader.py` — orchestrates a check-in + the Telegram propose/approve loop; scheduling entry point.
- `scripts/com.traid.trader-*.plist` — launchd jobs firing 3×/day (like the watchdog).
- End-of-run summary: P&L vs a buy-and-hold benchmark; honest "5 days = mostly luck" framing.

## Setup Martin must provide (all free/tiny; walk him through each)
1. **Alpaca paper account** → paper API key + secret.
2. **A new Telegram bot** (via @BotFather) → token (separate from the existing bot).
3. **Anthropic API key** for Fable 5 → pay-per-use (~15 calls total = pennies).
All in `.env` (gitignored). His Mac must be awake at check-in times (Argentina hours → US open/midday/close are daytime).

## Error handling / guardrails
Rails enforced in code; market-closed skip; halt-on-drawdown; no-reply = no trade; Alpaca/Fable API errors → notify + skip; idempotent (no double-placing on re-run).

## Testing
Unit: rails validator (caps enforced), signal-gatherer output shape (mocked tools), Alpaca client vs mocked REST, decide-parser with a mocked Fable response. Paper end-to-end verified manually before the 5-day run.

## Open items for tomorrow
Confirm this design → commit spec → `writing-plans` → subagent-driven build. Possible tweaks to revisit: exact check-in times in Martin's timezone, the Telegram approval command syntax, and whether to add new Python deps (alpaca-py/anthropic SDKs) vs thin stdlib REST clients.
