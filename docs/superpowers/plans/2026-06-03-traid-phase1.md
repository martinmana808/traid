# TRaid Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the conversation-first MVP of TRaid — an analyst skill, a free live-data tool, a portfolio/profile/notebook memory layer, and an append-only prediction ledger — so the user can have real, logged investment conversations grounded in live data inside this Claude Code project.

**Architecture:** TRaid is not a standalone app. It is a Claude Code skill (`.claude/skills/traid-analyst/SKILL.md`) that drives Claude to follow a fixed risk-first procedure, plus two small Python CLIs in `tools/` that print JSON (market data + ledger), plus `data/` files that hold persistent memory. Claude runs the tools via Bash and reads/edits the data files directly.

**Tech Stack:** Python 3, `yfinance` (free market data, US + NZX via `.NZ` suffix), `pytest`. Pure/parsing logic is unit-tested; live network fetches get a manually-run smoke test.

---

## File Structure

- `requirements.txt` — Python deps (`yfinance`, `pytest`)
- `conftest.py` — empty file at repo root so `pytest` puts the root on `sys.path` (lets tests import `tools.*`)
- `tools/__init__.py` — makes `tools` an importable package
- `tools/ledger.py` — append-only prediction ledger: `log()`, `list_entries()`, CLI
- `tools/market.py` — free market data: `normalize_ticker()`, `normalize_fx_pair()`, `error_response()`, live fetch wrappers, CLI
- `tests/__init__.py` — package marker
- `tests/test_ledger.py` — unit tests for ledger
- `tests/test_market.py` — unit tests for market pure functions
- `data/portfolio.json` — holdings, cash, risk tolerance
- `data/profile.md` — investor profile (goals, horizon, constraints)
- `data/notebook.md` — analyst's running theses & lessons
- `data/predictions.jsonl` — the ledger (starts empty)
- `.claude/skills/traid-analyst/SKILL.md` — the analyst persona + operating procedure
- `README.md` — how to set up and use TRaid

---

## Task 1: Project scaffolding & Python environment

**Files:**
- Create: `requirements.txt`
- Create: `conftest.py`
- Create: `tools/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create `requirements.txt`**

```
yfinance>=0.2.40
pytest>=8.0
```

- [ ] **Step 2: Create `conftest.py` (empty root marker)**

```python
# Present so pytest adds the repo root to sys.path, enabling `import tools.*` in tests.
```

- [ ] **Step 3: Create `tools/__init__.py`**

```python
# TRaid tools package.
```

- [ ] **Step 4: Create `tests/__init__.py`**

```python
# TRaid tests package.
```

- [ ] **Step 5: Create the virtualenv and install deps**

Run:
```bash
python3 -m venv .venv && ./.venv/bin/pip install -q -r requirements.txt && ./.venv/bin/python -c "import yfinance, pytest; print('deps ok')"
```
Expected: prints `deps ok` (may take ~30–60s on first install).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt conftest.py tools/__init__.py tests/__init__.py
git commit -m "chore: scaffold TRaid python project and deps"
```

---

## Task 2: Prediction ledger (`tools/ledger.py`)

**Files:**
- Create: `tools/ledger.py`
- Test: `tests/test_ledger.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ledger.py
import json
from pathlib import Path

from tools.ledger import log, list_entries, _next_id


def test_list_entries_empty_when_missing(tmp_path):
    assert list_entries(tmp_path / "nope.jsonl") == []


def test_log_appends_and_lists_roundtrip(tmp_path):
    path = tmp_path / "predictions.jsonl"
    entry = {
        "ticker": "VOO", "market": "US", "type": "long-term",
        "call": "buy", "rationale": "broad market DCA",
        "confidence": "medium", "horizon": "12 months",
        "reference_price": 512.30, "reference_currency": "USD",
    }
    saved = log(entry, path=path, today="2026-06-03")
    assert saved["id"] == "2026-06-03-001"
    assert saved["user_action"] is None
    assert saved["target"] is None

    entries = list_entries(path)
    assert len(entries) == 1
    assert entries[0]["ticker"] == "VOO"
    assert entries[0]["date"] == "2026-06-03"


def test_log_is_append_only_with_sequential_ids(tmp_path):
    path = tmp_path / "predictions.jsonl"
    log({"ticker": "VOO", "call": "buy"}, path=path, today="2026-06-03")
    log({"ticker": "AIR.NZ", "call": "hold"}, path=path, today="2026-06-03")
    log({"ticker": "MSFT", "call": "buy"}, path=path, today="2026-06-04")

    entries = list_entries(path)
    assert [e["id"] for e in entries] == [
        "2026-06-03-001", "2026-06-03-002", "2026-06-04-001",
    ]
    # file has exactly 3 lines (append-only, nothing rewritten)
    assert len([ln for ln in path.read_text().splitlines() if ln.strip()]) == 3


def test_list_entries_respects_limit(tmp_path):
    path = tmp_path / "predictions.jsonl"
    for _ in range(5):
        log({"ticker": "VOO", "call": "buy"}, path=path, today="2026-06-03")
    assert len(list_entries(path, limit=2)) == 2
    assert list_entries(path, limit=2)[-1]["id"] == "2026-06-03-005"


def test_next_id_counts_only_same_date():
    existing = [{"date": "2026-06-03"}, {"date": "2026-06-03"}, {"date": "2026-06-02"}]
    assert _next_id(existing, "2026-06-03") == "2026-06-03-003"
    assert _next_id(existing, "2026-06-04") == "2026-06-04-001"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/pytest tests/test_ledger.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.ledger'` (or import error).

- [ ] **Step 3: Write `tools/ledger.py`**

```python
"""Append-only prediction ledger for TRaid.

Usage (CLI):
    python tools/ledger.py log --ticker VOO --market US --type long-term \
        --call buy --confidence medium --horizon "12 months" \
        --reference-price 512.30 --reference-currency USD \
        --rationale "broad market DCA"
    python tools/ledger.py list [--limit N]
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "predictions.jsonl"

VALID_TYPES = {"long-term", "swing"}
VALID_CALLS = {"buy", "hold", "avoid", "trim", "sell"}
VALID_CONFIDENCE = {"low", "medium", "high"}


def list_entries(path=DEFAULT_PATH, limit=None):
    path = Path(path)
    if not path.exists():
        return []
    entries = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries[-limit:] if limit is not None else entries


def _next_id(existing, today):
    seq = sum(1 for e in existing if e.get("date") == today) + 1
    return f"{today}-{seq:03d}"


def log(entry, path=DEFAULT_PATH, today=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    today = today or date.today().isoformat()
    record = dict(entry)
    record.setdefault("date", today)
    record["id"] = _next_id(list_entries(path), record["date"])
    record.setdefault("target", None)
    record.setdefault("user_action", None)
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")
    return record


def _build_parser():
    p = argparse.ArgumentParser(description="TRaid prediction ledger")
    sub = p.add_subparsers(dest="cmd", required=True)

    lg = sub.add_parser("log", help="append a prediction")
    lg.add_argument("--ticker", required=True)
    lg.add_argument("--market", default="US")
    lg.add_argument("--type", dest="type_", choices=sorted(VALID_TYPES), default="long-term")
    lg.add_argument("--call", choices=sorted(VALID_CALLS), required=True)
    lg.add_argument("--rationale", default="")
    lg.add_argument("--confidence", choices=sorted(VALID_CONFIDENCE), default="medium")
    lg.add_argument("--horizon", default="")
    lg.add_argument("--reference-price", type=float, default=None)
    lg.add_argument("--reference-currency", default=None)
    lg.add_argument("--target", type=float, default=None)
    lg.add_argument("--path", default=str(DEFAULT_PATH))

    ls = sub.add_parser("list", help="list predictions")
    ls.add_argument("--limit", type=int, default=None)
    ls.add_argument("--path", default=str(DEFAULT_PATH))
    return p


def main(argv=None):
    args = _build_parser().parse_args(argv)
    if args.cmd == "log":
        entry = {
            "ticker": args.ticker, "market": args.market, "type": args.type_,
            "call": args.call, "rationale": args.rationale,
            "confidence": args.confidence, "horizon": args.horizon,
            "reference_price": args.reference_price,
            "reference_currency": args.reference_currency, "target": args.target,
        }
        print(json.dumps(log(entry, path=args.path), indent=2))
    elif args.cmd == "list":
        print(json.dumps(list_entries(args.path, limit=args.limit), indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/pytest tests/test_ledger.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Smoke-test the CLI**

Run:
```bash
./.venv/bin/python tools/ledger.py log --ticker VOO --call buy --confidence medium --horizon "12 months" --reference-price 512.30 --reference-currency USD --rationale "scaffold smoke test" --path /tmp/traid_smoke.jsonl && ./.venv/bin/python tools/ledger.py list --path /tmp/traid_smoke.jsonl && rm /tmp/traid_smoke.jsonl
```
Expected: prints the logged record (with an `id`) then a one-element list.

- [ ] **Step 6: Commit**

```bash
git add tools/ledger.py tests/test_ledger.py
git commit -m "feat: append-only prediction ledger with CLI"
```

---

## Task 3: Market data tool (`tools/market.py`)

**Files:**
- Create: `tools/market.py`
- Test: `tests/test_market.py`

- [ ] **Step 1: Write the failing tests (pure functions only — no network)**

```python
# tests/test_market.py
from tools.market import normalize_ticker, normalize_fx_pair, error_response


def test_normalize_ticker_us_unchanged():
    assert normalize_ticker("aapl") == "AAPL"
    assert normalize_ticker("VOO", market="US") == "VOO"


def test_normalize_ticker_nzx_gets_suffix():
    assert normalize_ticker("AIR", market="NZX") == "AIR.NZ"
    assert normalize_ticker("air", market="NZ") == "AIR.NZ"


def test_normalize_ticker_nzx_idempotent():
    assert normalize_ticker("AIR.NZ", market="NZX") == "AIR.NZ"


def test_normalize_fx_pair():
    assert normalize_fx_pair("NZDUSD") == "NZDUSD=X"
    assert normalize_fx_pair("nzd/usd") == "NZDUSD=X"
    assert normalize_fx_pair("NZDUSD=X") == "NZDUSD=X"


def test_error_response_shape():
    assert error_response("boom") == {"error": "boom"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/pytest tests/test_market.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.market'`.

- [ ] **Step 3: Write `tools/market.py`**

```python
"""Free market data CLI for TRaid (US + NZX via yfinance).

Usage (CLI):
    python tools/market.py quote AAPL
    python tools/market.py quote AIR --market NZX
    python tools/market.py history VOO 6mo
    python tools/market.py fundamentals MSFT
    python tools/market.py fx NZDUSD

Every command prints JSON. On any failure it prints {"error": "..."} and
exits 0 so the caller always gets parseable output.
"""
import argparse
import json
import sys


def normalize_ticker(ticker, market=None):
    t = ticker.strip().upper()
    if market and market.upper() in ("NZX", "NZ") and not t.endswith(".NZ"):
        t = f"{t}.NZ"
    return t


def normalize_fx_pair(pair):
    p = pair.strip().upper().replace("/", "")
    return p if p.endswith("=X") else f"{p}=X"


def error_response(message):
    return {"error": message}


def _yf():
    import yfinance as yf  # imported lazily so pure-function tests need no network/dep
    return yf


def quote(ticker, market=None):
    sym = normalize_ticker(ticker, market)
    try:
        info = _yf().Ticker(sym).fast_info
        return {
            "ticker": sym,
            "price": float(info["last_price"]),
            "previous_close": float(info["previous_close"]),
            "change_pct": round((float(info["last_price"]) / float(info["previous_close"]) - 1) * 100, 2),
            "currency": info["currency"],
        }
    except Exception as e:  # noqa: BLE001 — surface any failure as structured JSON
        return error_response(f"quote failed for {sym}: {e}")


def history(ticker, period, market=None):
    sym = normalize_ticker(ticker, market)
    try:
        df = _yf().Ticker(sym).history(period=period)
        if df.empty:
            return error_response(f"no history for {sym} ({period})")
        rows = [
            {
                "date": idx.date().isoformat(),
                "open": round(float(r["Open"]), 4),
                "high": round(float(r["High"]), 4),
                "low": round(float(r["Low"]), 4),
                "close": round(float(r["Close"]), 4),
                "volume": int(r["Volume"]),
            }
            for idx, r in df.iterrows()
        ]
        return {"ticker": sym, "period": period, "bars": rows}
    except Exception as e:  # noqa: BLE001
        return error_response(f"history failed for {sym}: {e}")


def fundamentals(ticker, market=None):
    sym = normalize_ticker(ticker, market)
    try:
        info = _yf().Ticker(sym).info
        keys = {
            "name": "shortName", "sector": "sector", "industry": "industry",
            "market_cap": "marketCap", "pe_ratio": "trailingPE",
            "dividend_yield": "dividendYield", "currency": "currency",
        }
        return {"ticker": sym, **{out: info.get(src) for out, src in keys.items()}}
    except Exception as e:  # noqa: BLE001
        return error_response(f"fundamentals failed for {sym}: {e}")


def fx(pair):
    sym = normalize_fx_pair(pair)
    try:
        rate = float(_yf().Ticker(sym).fast_info["last_price"])
        return {"pair": sym, "rate": rate}
    except Exception as e:  # noqa: BLE001
        return error_response(f"fx failed for {sym}: {e}")


def _build_parser():
    p = argparse.ArgumentParser(description="TRaid free market data")
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("quote"); q.add_argument("ticker"); q.add_argument("--market", default=None)
    h = sub.add_parser("history"); h.add_argument("ticker"); h.add_argument("period"); h.add_argument("--market", default=None)
    f = sub.add_parser("fundamentals"); f.add_argument("ticker"); f.add_argument("--market", default=None)
    x = sub.add_parser("fx"); x.add_argument("pair")
    return p


def main(argv=None):
    args = _build_parser().parse_args(argv)
    if args.cmd == "quote":
        out = quote(args.ticker, args.market)
    elif args.cmd == "history":
        out = history(args.ticker, args.period, args.market)
    elif args.cmd == "fundamentals":
        out = fundamentals(args.ticker, args.market)
    elif args.cmd == "fx":
        out = fx(args.pair)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/pytest tests/test_market.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Live smoke test (manual, needs network)**

Run:
```bash
./.venv/bin/python tools/market.py quote AAPL && ./.venv/bin/python tools/market.py fx NZDUSD
```
Expected: a JSON quote for AAPL with a real `price`, and a JSON `NZDUSD=X` rate. If offline, expect a clean `{"error": ...}` instead of a crash. (Note: `yfinance` field availability can vary; if `fundamentals` returns sparse fields that's acceptable — the contract is "valid JSON, never a crash.")

- [ ] **Step 6: Commit**

```bash
git add tools/market.py tests/test_market.py
git commit -m "feat: free market data tool (quote/history/fundamentals/fx)"
```

---

## Task 4: Persistent memory data files

**Files:**
- Create: `data/portfolio.json`
- Create: `data/profile.md`
- Create: `data/notebook.md`
- Create: `data/predictions.jsonl`

- [ ] **Step 1: Create `data/portfolio.json`**

```json
{
  "base_currency": "NZD",
  "cash_available": 0,
  "risk_tolerance": "conservative-moderate",
  "holdings": []
}
```

- [ ] **Step 2: Create `data/profile.md`**

```markdown
# Investor Profile — Martin

> TRaid reads this every session. Keep it short and current.

- **Broker:** Sharesies (New Zealand)
- **Base currency:** NZD
- **Markets:** US stocks/ETFs, NZX
- **Style:** Mix, leaning long-term; open to occasional shorter-term opportunities with explicit risk warnings.
- **Risk tolerance:** Conservative-moderate.
- **Experience:** Beginner — learning. Prefers clear explanations and risk-first reasoning.
- **Goals:** _(fill in: e.g. long-term wealth building, time horizon, target monthly contribution)_
- **Constraints / preferences:** _(fill in: sectors to avoid, ethical preferences, max position size, etc.)_
```

- [ ] **Step 3: Create `data/notebook.md`**

```markdown
# Analyst's Notebook

> TRaid's running log of open theses and lessons learned. Append over time; don't rewrite history.

## Open theses

_(none yet)_

## Lessons learned

_(none yet)_
```

- [ ] **Step 4: Create `data/predictions.jsonl` (empty)**

Create the file empty (the ledger appends to it):
```bash
: > data/predictions.jsonl
```

- [ ] **Step 5: Commit**

```bash
git add data/portfolio.json data/profile.md data/notebook.md data/predictions.jsonl
git commit -m "feat: persistent memory scaffolding (portfolio, profile, notebook, ledger file)"
```

---

## Task 5: The analyst skill (`.claude/skills/traid-analyst/SKILL.md`)

**Files:**
- Create: `.claude/skills/traid-analyst/SKILL.md`

- [ ] **Step 1: Write the skill**

```markdown
---
name: traid-analyst
description: Use whenever Martin asks for investment analysis, portfolio advice, what to buy/sell/hold, or how to deploy spare cash. TRaid is his personal, risk-first investment analyst with live data, persistent memory of his portfolio, and a self-verifying prediction ledger.
---

# TRaid — Personal Investment Analyst

You are TRaid: a seasoned, risk-first investment analyst sitting beside Martin, a **beginner** investor in **New Zealand** using **Sharesies**, investing in **US stocks/ETFs and NZX**, base currency **NZD**. This is his **real money**. You advise; he executes the trades himself.

## Non-negotiable stance
- You are a **personal decision-support tool, NOT licensed financial advice.** Say so when giving concrete recommendations.
- **Never invent a price or figure.** If a data fetch fails, say so and reason with what you have.
- **You are not psychic.** No one predicts markets with high accuracy. Your value is fewer mistakes, discipline, live data, right-sized positions, and a track record that improves over time. Be honest about uncertainty.

## Operating procedure — follow this EVERY time he asks for advice
1. **Load his context.** Read `data/portfolio.json`, `data/profile.md`, and `data/notebook.md`.
2. **Check your track record.** Read recent calls: `./.venv/bin/python tools/ledger.py list --limit 20`.
3. **Get live data** for every relevant ticker (never rely on memory for prices):
   - `./.venv/bin/python tools/market.py quote <TICKER> [--market NZX]`
   - `./.venv/bin/python tools/market.py history <TICKER> <PERIOD>`
   - `./.venv/bin/python tools/market.py fundamentals <TICKER>`
   - `./.venv/bin/python tools/market.py fx NZDUSD` (to value US holdings in NZD)
   - For NZX tickers pass `--market NZX` (e.g. `quote AIR --market NZX`).
4. **Think deeply before deciding.** For any actual buy/sell/sizing judgement, reason hard and explicitly: the bull case, the bear case, position sizing math, "what if I'm wrong," and confluence with his goals, risk tolerance, and existing holdings. Don't give snap takes on real-money decisions.
5. **Give sized, explained suggestions.** Always include: the specific action, how much (respecting `cash_available` and risk tolerance — never "all in"), the reasoning, the **downside/risk**, and a diversification check.
6. **Log every concrete call** to the ledger so the feedback loop has data:
   ```
   ./.venv/bin/python tools/ledger.py log --ticker <T> --market <US|NZX> \
     --type <long-term|swing> --call <buy|hold|avoid|trim|sell> \
     --confidence <low|medium|high> --horizon "<e.g. 12 months>" \
     --reference-price <live price> --reference-currency <USD|NZD> \
     --rationale "<one-line thesis>"
   ```
7. **Update the notebook** (`data/notebook.md`) when a new thesis or lesson emerges — append, don't rewrite.
8. **Keep the portfolio current.** When he tells you he bought/sold or has new cash, update `data/portfolio.json`.

## Guardrails
- Risk-first: size positions so no single wrong call hurts him badly; nudge diversification; never recommend going all-in.
- Surface your uncertainty and confidence level honestly.
- Match every suggestion to his goals, time horizon, and conservative-moderate risk tolerance.
- For NZX/US, remember currency: value and compare in NZD using the live FX rate.
- If `data/` files are missing or malformed, offer to initialise them rather than failing silently.

## First-run check
If `data/portfolio.json` shows no holdings and `cash_available` is 0, ask Martin to tell you his current holdings and how much he can invest, then update the files before advising.
```

- [ ] **Step 2: Verify the skill file is well-formed**

Run: `head -5 .claude/skills/traid-analyst/SKILL.md`
Expected: shows the YAML frontmatter with `name: traid-analyst` and a `description:` line.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/traid-analyst/SKILL.md
git commit -m "feat: traid-analyst skill (risk-first operating procedure)"
```

---

## Task 6: README & full test run

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
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
- Phase 2: technical indicators (RSI/MACD/Bollinger) + richer fundamentals.
- Phase 3: auto-verify matured predictions + self-calibrating scorecard.
```

- [ ] **Step 2: Run the full test suite**

Run: `./.venv/bin/pytest -v`
Expected: PASS (10 passed — 5 ledger + 5 market).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add TRaid README"
```

---

## Self-Review (completed by author)

**Spec coverage:**
- §5 architecture (skill + tools + data) → Tasks 1–5. ✓
- §6.1 analyst skill → Task 5. ✓
- §6.2 market tool (quote/history/fundamentals/fx, NZX normalisation, JSON errors) → Task 3. ✓
- §6.3 portfolio.json → Task 4. ✓
- §6.4 profile + notebook → Task 4. ✓
- §6.5 ledger (append-only, schema, log/list) → Task 2. ✓
- §7 data flow → encoded in the skill's operating procedure (Task 5). ✓
- §8 error handling (clean JSON errors, FX conversion, append-only) → Tasks 2, 3, 5. ✓
- §9 testing (ledger round-trip, market pure functions + manual smoke) → Tasks 2, 3, 6. ✓
- §10 safety/disclaimer → encoded in skill (Task 5). ✓
- Non-goals (indicators, verification, UI, broker sync) correctly absent. ✓

**Placeholder scan:** The only intentional fill-in blanks are in `data/profile.md` (user's personal goals/constraints) and `data/notebook.md` ("none yet") — these are runtime user content, not plan placeholders. No TBD/TODO in code or steps.

**Type consistency:** `log()`/`list_entries()`/`_next_id()` signatures match between `tools/ledger.py` and `tests/test_ledger.py`. `normalize_ticker()`/`normalize_fx_pair()`/`error_response()` match between `tools/market.py` and `tests/test_market.py`. Ledger entry field names match the spec §6.5 schema. CLI flag names in the skill (Task 5) match `ledger.py`'s argparse definitions (`--ticker`, `--market`, `--type`, `--call`, `--confidence`, `--horizon`, `--reference-price`, `--reference-currency`, `--rationale`) and `market.py`'s (`--market`, positional `ticker`/`period`/`pair`). ✓
