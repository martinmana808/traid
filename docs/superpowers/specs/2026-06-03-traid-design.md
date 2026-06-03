# TRaid — Design Spec (v1 / Phase 1)

- **Date:** 2026-06-03
- **Status:** Approved design — ready for implementation planning
- **Author:** Martin Mana (with Claude)

---

## 1. Summary

TRaid is a **personal investment-analyst assistant that lives inside this Claude Code project**. The user opens the project and talks to it the way they'd talk to a seasoned, 40-year-experienced stock analyst sitting beside them: *"Here's my portfolio, I've got $X to invest today — what should I do?"* It pulls the user's portfolio, fetches **free live market data** for US and NZX securities, reasons like a risk-first veteran, gives **sized, fully-explained suggestions**, and **logs every concrete call** to an immutable ledger so its track record becomes real and improvable over time.

**Claude is the analyst brain.** There is no separate LLM bill — TRaid runs on the user's existing Claude Code usage. Cost to run ≈ $0 beyond that (free market data, local files).

This is the reframe of an older, over-ambitious "TRaid" concept (probabilistic chart-pattern vision + self-training prediction engine). That concept's valuable kernel — **live data + a self-verifying prediction feedback loop** — survives here in a pragmatic, provable form.

---

## 2. Who it's for & what's at stake

- A **beginner investor** with a small (currently small-to-non-existent) portfolio, using **Sharesies** (New Zealand).
- Goal: go from *"I know almost nothing, my decisions are ~5% good"* to *"I consistently make sensible, risk-aware decisions and avoid catastrophic mistakes."*
- It is **decision support for the user's own real money.** The user executes trades themselves on Sharesies; TRaid advises.

### Honest framing (non-negotiable)

- TRaid is a **personal decision-support tool, not licensed financial advice.**
- It does **not** predict the market with high accuracy. No one can. The best investors are right on direction ~55–60% of the time. Any promise of "95% accuracy" is false and will not be built toward.
- The real, achievable win is **fewer mistakes, real discipline, live ground-truth, risk-appropriate sizing, and a system that gets sharper the longer it's used.**

---

## 3. Why TRaid beats a normal Claude conversation (the moats)

A single-turn answer from TRaid and from vanilla Claude can look similar. The value is in what **persists and compounds**. Four things a stateless chat structurally cannot do:

1. **Live ground-truth.** TRaid fetches *today's* actual prices, fundamentals, and NZD/USD FX. Vanilla Claude guesses from a training cutoff.
2. **Permanent knowledge of the user.** Holdings, cash, cost basis, risk tolerance, goals, and NZ/Sharesies/NZD constraints are loaded every session. A normal chat forgets everything next time.
3. **A self-verifying track record.** Every call is logged; later TRaid checks whether it was right and feeds that back ("my swing flags have only been ~38% right — weight them lightly"). No generic chat has accountability or memory of being wrong. **This is the core moat and it compounds.**
4. **Enforced discipline.** The skill forces the same rigorous process every time (live data → the user's book → track record → sizing → downside → log). Normal-chat quality swings with prompting; TRaid makes the good process automatic.

---

## 4. Goals & non-goals

### Goals (Phase 1)
- Have a **real, logged analyst conversation today**, grounded in live data and the user's actual portfolio.
- Establish the **persistent memory** (portfolio, investor profile, analyst notebook) that makes every session well-informed.
- Start the **feedback loop** by logging every concrete call richly from day one.
- **Risk-first guardrails** baked into every recommendation.
- Use **deliberate deep/extended reasoning** for actual buy/sell/sizing decisions.

### Non-goals (explicitly out of Phase 1 — YAGNI)
- Technical indicators (RSI/MACD/Bollinger) → **Phase 2**
- Automatic verification of matured predictions + self-calibrating scorecard → **Phase 3**
- Charting / visual UI of any kind
- Brokerage (Sharesies) sync — no safe official API exists; manual entry instead
- Real-time / intraday tick data, news & sentiment feeds
- Tax computation (NZ FIF etc.) — light *awareness* only, no calculation
- Multi-user / accounts / web app

---

## 5. Architecture

TRaid is **not a standalone application.** It is a set of artifacts inside this Claude Code project:

```
TRaid/
├─ .claude/skills/traid-analyst/SKILL.md   # the analyst persona + operating procedure
├─ tools/
│  ├─ market.py                            # free live data CLI (yfinance) → JSON
│  └─ ledger.py                            # append/list prediction ledger
├─ data/
│  ├─ portfolio.json                       # holdings, cash, risk tolerance
│  ├─ profile.md                           # investor profile (goals, horizon, constraints)
│  ├─ notebook.md                          # analyst's running theses & lessons
│  └─ predictions.jsonl                    # immutable, append-only call ledger
├─ requirements.txt                        # python deps (yfinance, pytest)
├─ tests/                                  # unit tests for tools
└─ docs/superpowers/specs/                 # this spec + future ones
```

**Interaction model:** the user opens this project in Claude Code and chats. The `traid-analyst` skill governs Claude's behaviour; Claude uses the **Bash** tool to run `tools/*.py`, and the **Read/Edit** tools to read and update the `data/` files.

**Tech stack:** Python 3 + [`yfinance`](https://pypi.org/project/yfinance/) (free data, covers US tickers and NZX via the `.NZ` suffix). Tools are small CLIs that print JSON to stdout so Claude can consume them. `pytest` for tests.

---

## 6. Components (Phase 1)

### 6.1 The analyst skill — `.claude/skills/traid-analyst/SKILL.md`
Defines:
- **Persona:** seasoned, risk-first, honest, educational; NZ-context-aware (NZD base currency, Sharesies as the broker).
- **Operating procedure (fixed, every advice request):**
  1. Read `data/portfolio.json`, `data/profile.md`, recent `data/notebook.md`.
  2. Read recent entries from `data/predictions.jsonl`.
  3. Fetch current data for relevant tickers via `tools/market.py`.
  4. **Engage extended/deep reasoning** for the decision: bull case, bear case, position sizing math, "what if I'm wrong," confluence with the user's goals and existing holdings.
  5. Give **sized, explained suggestions** (how much, why, the downside, the risk).
  6. **Log** every concrete call to the ledger via `tools/ledger.py`.
  7. Update `notebook.md` when a thesis or lesson emerges.
- **Guardrails:** position sizing, diversification nudges, never "all-in," surface uncertainty, respect available cash and risk tolerance, always frame as decision-support not licensed advice.
- **Hard rule:** **never invent a price or figure.** If a data fetch fails, say so and proceed honestly.

### 6.2 Market data tool — `tools/market.py`
A CLI (Python + `yfinance`) printing JSON. Subcommands:
- `quote <TICKER>` — latest price, day change, currency.
- `history <TICKER> <PERIOD>` — OHLCV series (e.g. `6mo`, `1y`).
- `fundamentals <TICKER>` — P/E, market cap, dividend yield, basic profile.
- `fx <PAIR>` — e.g. `NZDUSD` for currency conversion.

Handles US tickers directly and NZX via `.NZ` (the skill/tool normalises e.g. `AIR` → `AIR.NZ`). On bad ticker or network error, prints a structured JSON error (never crashes silently).

### 6.3 Portfolio store — `data/portfolio.json`
```json
{
  "base_currency": "NZD",
  "cash_available": 0,
  "risk_tolerance": "conservative-moderate",
  "holdings": [
    { "ticker": "VOO", "market": "US", "shares": 0, "avg_cost": 0, "currency": "USD" }
  ]
}
```
Read/updated directly by Claude. US holdings are valued in USD then converted to NZD via the live FX rate.

### 6.4 Investor profile & analyst notebook
- `data/profile.md` — goals, time horizon, constraints, what the user understands/avoids. Slowly-changing context loaded every session.
- `data/notebook.md` — the analyst's running markdown of **open theses and lessons learned**, so context deepens instead of resetting.

### 6.5 Prediction ledger — `data/predictions.jsonl` + `tools/ledger.py`
Append-only JSONL. `ledger.py log` appends safely; `ledger.py list` reads back recent calls. Each entry:
```json
{
  "id": "2026-06-03-001",
  "date": "2026-06-03",
  "ticker": "VOO",
  "market": "US",
  "type": "long-term",            // "long-term" | "swing"
  "call": "buy",                  // "buy" | "hold" | "avoid" | "trim" | "sell"
  "rationale": "short reasoning summary",
  "confidence": "medium",         // low | medium | high
  "horizon": "12 months",
  "reference_price": 512.30,       // price AT the moment of the call
  "reference_currency": "USD",
  "target": null,                  // optional
  "user_action": null              // what the user actually did, filled in later
}
```
This is the seed of the feedback loop. Logging richly **now** gives Phase 3's verification real data to grade.

---

## 7. Data flow (Phase 1)

```
user message
  → traid-analyst skill engages
  → read portfolio.json + profile.md + notebook.md
  → read recent predictions.jsonl
  → (Bash) tools/market.py quote/history/fundamentals/fx
  → DEEP reasoning: bull / bear / sizing / "if I'm wrong"
  → sized, explained suggestions with stated risk
  → (Bash) tools/ledger.py log  → append each concrete call
  → update notebook.md if a thesis/lesson emerged
  → reply to user
```

---

## 8. Error handling
- Bad ticker / network failure → tool prints a clean JSON error; the analyst reports it honestly rather than guessing.
- Currency: US holdings valued in USD, converted to NZD via live FX; if FX fetch fails, the analyst flags the limitation.
- Ledger writes are **append-only** — history is never rewritten or deleted.
- Malformed/missing data files → the skill detects and offers to initialise them rather than failing opaquely.

---

## 9. Testing
- **`tools/ledger.py`:** unit tests for append + list round-trip (using a temp file), and schema validity of written entries.
- **`tools/market.py`:** unit tests for output shape and ticker normalisation against a **recorded fixture**, so tests don't depend on the live network. A separate, manually-run smoke test hits the real API.
- The analyst's judgement is validated by **actually using it** — there is no unit test for "good advice."

---

## 10. Safety & disclaimer
- Every advice surface reiterates: **personal decision-support tool, not licensed financial advice.**
- Risk-first by construction: sizing, diversification, downside-always-stated, never all-in.
- No fabricated data, ever.
- The user executes all trades themselves; TRaid never has brokerage access or the ability to move money.

---

## 11. Roadmap (post Phase 1)
- **Phase 2 — the engine:** technical indicators (RSI, MACD, Bollinger Bands) computed from OHLCV + richer fundamentals/news, so swing flags rest on real confluence rather than vibes.
- **Phase 3 — the logbook (where "self-correcting" becomes real):** automatically verify matured predictions against actual prices, compute the error/outcome, and feed an honest, **calibrated** track record back into future advice (e.g. down-weighting historically-unreliable call types, surfacing calibration of confidence vs. realised hit-rate).

Each phase gets its own spec → plan → implementation cycle.

---

## 12. Decisions on record
| Decision | Choice | Rationale |
|---|---|---|
| Purpose | Decision support for the user's own trading | User intent |
| Style | Mix, leaning long-term | User choice; safest for a beginner |
| Markets | US stocks/ETFs + NZX | User's actual Sharesies markets |
| Data | Free (yfinance) | Adequate for long-term/swing; $0 |
| Portfolio input | Manual (`portfolio.json`) | No safe Sharesies API; zero credential risk |
| Brain host | Inside Claude Code | Best reasoning, $0 extra, matches "use my Claude login" legitimately |
| Build order | A — conversation-first, then engine, then logbook | Fastest to a usable, trustworthy loop |
| Risk default | Conservative-moderate | Beginner, real money; user accepted |
| Reasoning depth | Deep/extended thinking for decisions | Real-money calls deserve slow thinking |
