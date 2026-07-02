# TRaid Autopilot (paper) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A fully local paper-trading bot that runs every US-market hour for 5 days, lets an AI brain (Fable 5, then Opus 4.8) propose long-only trades on the watchlist within code-enforced rails, and writes a plain-text status file the user checks.

**Architecture:** Pure-Python core (broker, rails, clock, news, fundamentals cache, status renderer) is fully unit-tested offline. A thin `autopilot.py` CLI exposes three verbs — `prepare` (emit a market snapshot + today's brain model), `execute` (validate proposed orders through the rails, fill survivors, rewrite the status file), and `brain-model` (print today's model id). A shell wrapper + hourly `launchd` job runs a headless `claude -p` session whose own model IS the brain: it reads `prepare`, decides orders, and calls `execute`.

**Tech Stack:** Python 3, stdlib (`json`, `datetime`, `zoneinfo`, `pathlib`), `pandas`/`numpy` (already used), `yfinance` (already a dep, for news), existing `tools/indicators.py` + `tools/fundamentals.py` + `tools/market.py`. Tests: `pytest` (already used). Scheduling: macOS `launchd` + `caffeinate` + the `claude` CLI.

## Global Constraints

- **Decision-support tool, NOT licensed financial advice.** Paper money only — no real orders, no broker account, no API keys.
- **Capital:** $5,000.00 simulated starting capital.
- **Universe:** tickers in `watchlist.json` (project root) ONLY — a hard whitelist.
- **Rails enforced in code (`tools/autopilot_rails.py`), never only in a prompt:** long-only (no shorting), no leverage (no spending cash it lacks), watchlist-only, ≤40% of total account value per name, circuit breaker halting new buys at −25% from start, and no fills when the US market is closed.
- **Trading style:** long-only; same-day (day) trading is allowed.
- **Brain by date (America/New_York date):** `claude-fable-5` on/before 2026-07-07, `claude-opus-4-8` after. Run window: Mon Jul 6 → Fri Jul 10 2026.
- **All new runtime data lives under `data/autopilot/` and is gitignored.** Never commit account/trades/status/cache files.
- **Follow existing tool conventions:** `sys.path.insert` shim at top so `tools.*` imports work under both CLI and pytest; failures surface as structured data, not crashes; money math rounds to cents.
- **Existing tools reused, not reimplemented:** `tools.indicators.analyze`, `tools.fundamentals.analyze`, `tools.market.quote`.

---

## Task 1: Paper broker core

Pure account math — the single source of truth for cash, positions, and P&L. No network. All money rounds to cents.

**Files:**
- Create: `tools/autopilot_broker.py`
- Test: `tests/test_autopilot_broker.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `new_account(starting_capital=5000.0) -> dict` → `{"starting_capital", "cash", "positions": [], "halted": False}` (positions items are `{"ticker","shares","avg_cost"}`).
  - `position_shares(account, ticker) -> float`
  - `apply_fill(account, side, ticker, shares, price) -> dict` (returns a NEW account dict; `side` in `{"buy","sell"}`; raises `ValueError` on insufficient cash or overselling)
  - `mark_to_market(account, prices) -> dict` → `{"cash","invested","total_value","pnl_abs","pnl_pct","positions":[{"ticker","shares","avg_cost","price","value","pnl_abs","pnl_pct"}]}` (`prices` maps ticker→float; missing price falls back to `avg_cost`)
  - `load_account(path) -> dict`, `save_account(account, path) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autopilot_broker.py
import math
import pytest
from tools.autopilot_broker import (
    new_account, position_shares, apply_fill, mark_to_market,
    load_account, save_account,
)


def test_new_account_defaults():
    a = new_account()
    assert a["starting_capital"] == 5000.0
    assert a["cash"] == 5000.0
    assert a["positions"] == []
    assert a["halted"] is False


def test_buy_reduces_cash_and_opens_position():
    a = apply_fill(new_account(1000.0), "buy", "NVDA", 2, 100.0)
    assert a["cash"] == 800.0
    assert position_shares(a, "NVDA") == 2
    assert a["positions"][0]["avg_cost"] == 100.0


def test_buy_again_averages_cost():
    a = new_account(1000.0)
    a = apply_fill(a, "buy", "NVDA", 2, 100.0)   # 200
    a = apply_fill(a, "buy", "NVDA", 2, 200.0)   # 400
    assert position_shares(a, "NVDA") == 4
    assert a["positions"][0]["avg_cost"] == 150.0
    assert a["cash"] == 400.0


def test_sell_returns_cash_keeps_avg_cost_and_removes_when_flat():
    a = new_account(1000.0)
    a = apply_fill(a, "buy", "NVDA", 4, 100.0)   # cash 600
    a = apply_fill(a, "sell", "NVDA", 4, 120.0)  # cash 600+480
    assert a["cash"] == 1080.0
    assert position_shares(a, "NVDA") == 0
    assert a["positions"] == []


def test_buy_over_cash_raises():
    with pytest.raises(ValueError):
        apply_fill(new_account(100.0), "buy", "NVDA", 2, 100.0)


def test_oversell_raises():
    a = apply_fill(new_account(1000.0), "buy", "NVDA", 1, 100.0)
    with pytest.raises(ValueError):
        apply_fill(a, "sell", "NVDA", 2, 100.0)


def test_mark_to_market_pnl():
    a = new_account(1000.0)
    a = apply_fill(a, "buy", "NVDA", 4, 100.0)   # cash 600, cost 400
    m = mark_to_market(a, {"NVDA": 150.0})
    assert m["cash"] == 600.0
    assert m["invested"] == 600.0                 # 4 * 150
    assert m["total_value"] == 1200.0
    assert m["pnl_abs"] == 200.0
    assert m["pnl_pct"] == 20.0
    pos = m["positions"][0]
    assert pos["value"] == 600.0 and pos["pnl_pct"] == 50.0


def test_mark_to_market_missing_price_uses_cost():
    a = apply_fill(new_account(1000.0), "buy", "NVDA", 4, 100.0)
    m = mark_to_market(a, {})  # no price
    assert m["positions"][0]["price"] == 100.0
    assert m["pnl_abs"] == 0.0


def test_save_and_load_roundtrip(tmp_path):
    p = tmp_path / "account.json"
    a = apply_fill(new_account(1000.0), "buy", "NVDA", 1, 100.0)
    save_account(a, str(p))
    assert load_account(str(p)) == a
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_autopilot_broker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.autopilot_broker'`

- [ ] **Step 3: Write minimal implementation**

```python
# tools/autopilot_broker.py
"""Local paper broker for TRaid Autopilot — pure account math, no network.

The account is a plain dict persisted as JSON. All money rounds to cents.
Rails live in autopilot_rails.py; this module only mutates state and never
decides whether a trade is *allowed* (beyond physical impossibility).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _cents(x):
    return round(float(x), 2)


def new_account(starting_capital=5000.0):
    return {
        "starting_capital": _cents(starting_capital),
        "cash": _cents(starting_capital),
        "positions": [],   # [{"ticker","shares","avg_cost"}]
        "halted": False,
    }


def _find(account, ticker):
    for p in account["positions"]:
        if p["ticker"] == ticker:
            return p
    return None


def position_shares(account, ticker):
    p = _find(account, ticker)
    return p["shares"] if p else 0


def apply_fill(account, side, ticker, shares, price):
    import copy
    a = copy.deepcopy(account)
    shares = float(shares)
    price = float(price)
    if shares <= 0:
        raise ValueError("shares must be positive")
    pos = _find(a, ticker)
    if side == "buy":
        cost = shares * price
        if cost > a["cash"] + 1e-9:
            raise ValueError(f"insufficient cash: need {cost}, have {a['cash']}")
        a["cash"] = _cents(a["cash"] - cost)
        if pos:
            total = pos["shares"] + shares
            pos["avg_cost"] = _cents((pos["shares"] * pos["avg_cost"] + cost) / total)
            pos["shares"] = total
        else:
            a["positions"].append({"ticker": ticker, "shares": shares, "avg_cost": _cents(price)})
    elif side == "sell":
        if not pos or shares > pos["shares"] + 1e-9:
            raise ValueError(f"cannot sell {shares} {ticker}: holding {position_shares(a, ticker)}")
        a["cash"] = _cents(a["cash"] + shares * price)
        pos["shares"] -= shares
        if pos["shares"] <= 1e-9:
            a["positions"] = [p for p in a["positions"] if p["ticker"] != ticker]
    else:
        raise ValueError(f"unknown side: {side}")
    # normalise whole-share counts to int when clean
    for p in a["positions"]:
        if abs(p["shares"] - round(p["shares"])) < 1e-9:
            p["shares"] = int(round(p["shares"]))
    return a


def mark_to_market(account, prices):
    positions = []
    invested = 0.0
    for p in account["positions"]:
        price = float(prices.get(p["ticker"], p["avg_cost"]))
        value = p["shares"] * price
        cost = p["shares"] * p["avg_cost"]
        invested += value
        positions.append({
            "ticker": p["ticker"], "shares": p["shares"], "avg_cost": _cents(p["avg_cost"]),
            "price": _cents(price), "value": _cents(value),
            "pnl_abs": _cents(value - cost),
            "pnl_pct": round((price / p["avg_cost"] - 1) * 100, 2) if p["avg_cost"] else 0.0,
        })
    total = account["cash"] + invested
    start = account["starting_capital"]
    return {
        "cash": _cents(account["cash"]),
        "invested": _cents(invested),
        "total_value": _cents(total),
        "pnl_abs": _cents(total - start),
        "pnl_pct": round((total / start - 1) * 100, 2) if start else 0.0,
        "positions": positions,
    }


def load_account(path):
    with open(path) as f:
        return json.load(f)


def save_account(account, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(account, f, indent=2)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_autopilot_broker.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add tools/autopilot_broker.py tests/test_autopilot_broker.py
git commit -m "feat(autopilot): local paper broker core (fills, mark-to-market, persistence)"
```

---

## Task 2: Rails validator

Pure order validation — the safety core. Every proposed order passes through here before any fill.

**Files:**
- Create: `tools/autopilot_rails.py`
- Test: `tests/test_autopilot_rails.py`

**Interfaces:**
- Consumes: `tools.autopilot_broker.mark_to_market`, `position_shares`.
- Produces:
  - `MAX_POSITION_PCT = 0.40`, `CIRCUIT_BREAKER_PCT = -25.0`
  - `is_halted(account, prices) -> bool` (True when marked `pnl_pct <= -25.0`)
  - `validate_order(order, account, prices, watchlist, market_open, halted) -> (bool, str)` where `order = {"side","ticker","shares"}`. Returns `(True, "ok")` or `(False, reason)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autopilot_rails.py
from tools.autopilot_broker import new_account, apply_fill
from tools.autopilot_rails import is_halted, validate_order

WL = ["NVDA", "META"]


def _acct():
    return new_account(1000.0)


def test_market_closed_rejects():
    ok, why = validate_order({"side": "buy", "ticker": "NVDA", "shares": 1},
                             _acct(), {"NVDA": 100.0}, WL, market_open=False, halted=False)
    assert not ok and "closed" in why.lower()


def test_off_watchlist_rejects():
    ok, why = validate_order({"side": "buy", "ticker": "TSLA", "shares": 1},
                             _acct(), {"TSLA": 100.0}, WL, market_open=True, halted=False)
    assert not ok and "watchlist" in why.lower()


def test_bad_shares_rejects():
    ok, why = validate_order({"side": "buy", "ticker": "NVDA", "shares": 0},
                             _acct(), {"NVDA": 100.0}, WL, market_open=True, halted=False)
    assert not ok


def test_leverage_rejects():
    ok, why = validate_order({"side": "buy", "ticker": "NVDA", "shares": 20},
                             _acct(), {"NVDA": 100.0}, WL, market_open=True, halted=False)
    assert not ok and "cash" in why.lower()


def test_over_40pct_rejects():
    # $1000 account, buying $500 of one name = 50% > 40%
    ok, why = validate_order({"side": "buy", "ticker": "NVDA", "shares": 5},
                             _acct(), {"NVDA": 100.0}, WL, market_open=True, halted=False)
    assert not ok and "40" in why


def test_within_40pct_and_cash_ok():
    ok, why = validate_order({"side": "buy", "ticker": "NVDA", "shares": 3},
                             _acct(), {"NVDA": 100.0}, WL, market_open=True, halted=False)
    assert ok


def test_halted_blocks_buys_but_allows_sells():
    a = apply_fill(_acct(), "buy", "NVDA", 3, 100.0)
    buy_ok, _ = validate_order({"side": "buy", "ticker": "META", "shares": 1},
                               a, {"NVDA": 100.0, "META": 100.0}, WL, market_open=True, halted=True)
    sell_ok, _ = validate_order({"side": "sell", "ticker": "NVDA", "shares": 1},
                                a, {"NVDA": 100.0}, WL, market_open=True, halted=True)
    assert not buy_ok and sell_ok


def test_short_sell_rejects():
    ok, why = validate_order({"side": "sell", "ticker": "NVDA", "shares": 1},
                             _acct(), {"NVDA": 100.0}, WL, market_open=True, halted=False)
    assert not ok and ("hold" in why.lower() or "own" in why.lower())


def test_is_halted_trips_at_minus_25():
    a = apply_fill(new_account(1000.0), "buy", "NVDA", 10, 100.0)  # all-in, cost 1000
    assert is_halted(a, {"NVDA": 74.0}) is True    # -26%
    assert is_halted(a, {"NVDA": 80.0}) is False   # -20%
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_autopilot_rails.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.autopilot_rails'`

- [ ] **Step 3: Write minimal implementation**

```python
# tools/autopilot_rails.py
"""Hard risk rails for TRaid Autopilot — enforced in code, not the prompt.

validate_order is the ONLY gate between an AI proposal and a real fill.
Long-only, no leverage, watchlist-only, <=40% per name, market-open, and a
-25% circuit breaker that blocks new buys.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.autopilot_broker import mark_to_market, position_shares

MAX_POSITION_PCT = 0.40
CIRCUIT_BREAKER_PCT = -25.0


def is_halted(account, prices):
    return mark_to_market(account, prices)["pnl_pct"] <= CIRCUIT_BREAKER_PCT


def validate_order(order, account, prices, watchlist, market_open, halted):
    side = order.get("side")
    ticker = order.get("ticker")
    shares = order.get("shares", 0)

    if not market_open:
        return False, "market closed — no fills"
    if ticker not in watchlist:
        return False, f"{ticker} not on watchlist"
    if side not in ("buy", "sell"):
        return False, f"invalid side {side!r}"
    try:
        shares = float(shares)
    except (TypeError, ValueError):
        return False, "shares not a number"
    if shares <= 0:
        return False, "shares must be positive"
    price = prices.get(ticker)
    if price is None or price <= 0:
        return False, f"no live price for {ticker}"

    if side == "sell":
        if shares > position_shares(account, ticker) + 1e-9:
            return False, f"cannot sell {shares} {ticker} — hold {position_shares(account, ticker)} (long-only, no shorting)"
        return True, "ok"

    # side == buy
    if halted:
        return False, "circuit breaker halted — no new buys (down >=25%)"
    cost = shares * price
    if cost > account["cash"] + 1e-9:
        return False, f"insufficient cash — need ${cost:.2f}, have ${account['cash']:.2f} (no leverage)"
    marked = mark_to_market(account, prices)
    total = marked["total_value"]                       # a buy shifts cash->shares; total unchanged
    existing = next((p["value"] for p in marked["positions"] if p["ticker"] == ticker), 0.0)
    if total > 0 and (existing + cost) > MAX_POSITION_PCT * total + 1e-9:
        pct = (existing + cost) / total * 100
        return False, f"{ticker} would be {pct:.0f}% of account — over 40% cap"
    return True, "ok"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_autopilot_rails.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add tools/autopilot_rails.py tests/test_autopilot_rails.py
git commit -m "feat(autopilot): code-enforced risk rails (long-only, no leverage, 40% cap, -25% breaker)"
```

---

## Task 3: Market clock + brain selector

Pure time logic: is the US market open right now, and which model is today's brain.

**Files:**
- Create: `tools/autopilot_clock.py`
- Test: `tests/test_autopilot_clock.py`

**Interfaces:**
- Consumes: nothing (stdlib `datetime`, `zoneinfo`).
- Produces:
  - `is_market_open(now_utc) -> bool` (`now_utc` a tz-aware UTC datetime)
  - `brain_model_for(ny_date) -> str` (`"claude-fable-5"` if `ny_date <= date(2026,7,7)` else `"claude-opus-4-8"`)
  - `brain_label(model) -> str` (`"Fable 5"` / `"Opus 4.8"` / else the raw id)
  - `US_MARKET_HOLIDAYS` (a `set[date]` incl. `date(2026,7,3)`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autopilot_clock.py
from datetime import datetime, date, timezone
from tools.autopilot_clock import is_market_open, brain_model_for, brain_label

# Mon Jul 6 2026, 14:00 UTC == 10:00 ET (EDT) -> open
OPEN_UTC = datetime(2026, 7, 6, 14, 0, tzinfo=timezone.utc)
# Mon Jul 6 2026, 21:00 UTC == 17:00 ET -> after close
AFTER_UTC = datetime(2026, 7, 6, 21, 0, tzinfo=timezone.utc)
# Sat Jul 4 2026, 14:00 UTC -> weekend
WEEKEND_UTC = datetime(2026, 7, 4, 14, 0, tzinfo=timezone.utc)
# Fri Jul 3 2026, 14:00 UTC -> holiday (Independence Day observed)
HOLIDAY_UTC = datetime(2026, 7, 3, 14, 0, tzinfo=timezone.utc)


def test_open_during_session():
    assert is_market_open(OPEN_UTC) is True


def test_closed_after_hours():
    assert is_market_open(AFTER_UTC) is False


def test_closed_on_weekend():
    assert is_market_open(WEEKEND_UTC) is False


def test_closed_on_holiday():
    assert is_market_open(HOLIDAY_UTC) is False


def test_brain_is_fable_through_jul7():
    assert brain_model_for(date(2026, 7, 6)) == "claude-fable-5"
    assert brain_model_for(date(2026, 7, 7)) == "claude-fable-5"


def test_brain_is_opus_from_jul8():
    assert brain_model_for(date(2026, 7, 8)) == "claude-opus-4-8"


def test_brain_labels():
    assert brain_label("claude-fable-5") == "Fable 5"
    assert brain_label("claude-opus-4-8") == "Opus 4.8"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_autopilot_clock.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.autopilot_clock'`

- [ ] **Step 3: Write minimal implementation**

```python
# tools/autopilot_clock.py
"""US market-open check + date-based brain selection for TRaid Autopilot.

Market hours: Mon-Fri 09:30-16:00 America/New_York, excluding NYSE holidays.
The 2026 holiday set covers the run window (notably Fri Jul 3, the observed
Independence Day, since Jul 4 2026 is a Saturday).
"""
from datetime import date, time
from zoneinfo import ZoneInfo

_NY = ZoneInfo("America/New_York")
_OPEN = time(9, 30)
_CLOSE = time(16, 0)

US_MARKET_HOLIDAYS = {
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 19),  # MLK Jr. Day
    date(2026, 2, 16),  # Washington's Birthday
    date(2026, 4, 3),   # Good Friday
    date(2026, 5, 25),  # Memorial Day
    date(2026, 6, 19),  # Juneteenth
    date(2026, 7, 3),   # Independence Day (observed; Jul 4 is a Saturday)
    date(2026, 9, 7),   # Labor Day
    date(2026, 11, 26), # Thanksgiving
    date(2026, 12, 25), # Christmas
}


def is_market_open(now_utc):
    ny = now_utc.astimezone(_NY)
    if ny.weekday() >= 5:            # Sat/Sun
        return False
    if ny.date() in US_MARKET_HOLIDAYS:
        return False
    return _OPEN <= ny.time() < _CLOSE


def brain_model_for(ny_date):
    return "claude-fable-5" if ny_date <= date(2026, 7, 7) else "claude-opus-4-8"


def brain_label(model):
    return {"claude-fable-5": "Fable 5", "claude-opus-4-8": "Opus 4.8"}.get(model, model)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_autopilot_clock.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add tools/autopilot_clock.py tests/test_autopilot_clock.py
git commit -m "feat(autopilot): US market-open guard + date-based Fable/Opus brain selector"
```

---

## Task 4: News fetch

Thin wrapper over `yfinance`'s free per-ticker news, normalised to the few fields the brain needs. Network is injectable so tests stay offline.

**Files:**
- Create: `tools/autopilot_news.py`
- Test: `tests/test_autopilot_news.py`

**Interfaces:**
- Consumes: nothing (lazy `yfinance` import).
- Produces: `headlines(ticker, limit=3, _fetch=None) -> list[dict]` where each item is `{"title","source","published","url"}`. `_fetch(ticker) -> list[raw]` is injectable; default calls yfinance. Never raises — returns `[]` on any error.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autopilot_news.py
from tools.autopilot_news import headlines

RAW = [
    {"content": {
        "title": "Palantir jumps on upgrade",
        "pubDate": "2026-07-02T14:12:51Z",
        "provider": {"displayName": "Yahoo Finance"},
        "canonicalUrl": {"url": "https://example.com/a"},
    }},
    {"content": {
        "title": "Chip demand strong",
        "pubDate": "2026-07-02T13:00:00Z",
        "provider": {"displayName": "Reuters"},
        "clickThroughUrl": {"url": "https://example.com/b"},
    }},
    {"content": {"title": "Third story", "pubDate": "", "provider": {}}},
    {"content": {"title": "Fourth story", "pubDate": "", "provider": {}}},
]


def test_headlines_normalises_and_limits():
    out = headlines("NVDA", limit=3, _fetch=lambda t: RAW)
    assert len(out) == 3
    assert out[0] == {
        "title": "Palantir jumps on upgrade",
        "source": "Yahoo Finance",
        "published": "2026-07-02T14:12:51Z",
        "url": "https://example.com/a",
    }
    assert out[1]["url"] == "https://example.com/b"
    assert out[2]["source"] == ""  # missing provider degrades to empty string


def test_headlines_swallows_errors():
    def boom(_):
        raise RuntimeError("network down")
    assert headlines("NVDA", _fetch=boom) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_autopilot_news.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.autopilot_news'`

- [ ] **Step 3: Write minimal implementation**

```python
# tools/autopilot_news.py
"""Free per-ticker headlines for TRaid Autopilot via yfinance.

Headlines only — no deep analysis. News-sentiment is noisy; the brain treats
these as a hint, like the momentum indicators. Never raises: returns [] on any
failure so one bad ticker can't sink a run.
"""


def _yf_fetch(ticker):
    import yfinance as yf
    return yf.Ticker(ticker).news or []


def _url(content):
    for key in ("canonicalUrl", "clickThroughUrl"):
        node = content.get(key) or {}
        if node.get("url"):
            return node["url"]
    return ""


def headlines(ticker, limit=3, _fetch=None):
    fetch = _fetch or _yf_fetch
    try:
        raw = fetch(ticker) or []
    except Exception:  # noqa: BLE001 — a bad news feed must not sink the run
        return []
    out = []
    for item in raw[:limit]:
        c = item.get("content", {}) if isinstance(item, dict) else {}
        out.append({
            "title": c.get("title", ""),
            "source": (c.get("provider") or {}).get("displayName", ""),
            "published": c.get("pubDate", ""),
            "url": _url(c),
        })
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_autopilot_news.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add tools/autopilot_news.py tests/test_autopilot_news.py
git commit -m "feat(autopilot): free per-ticker news headlines (yfinance, error-swallowing)"
```

---

## Task 5: Fundamentals daily cache

Fundamentals barely move intraday, so fetch once per NY date and reuse. Keeps the hourly snapshot lean.

**Files:**
- Create: `tools/autopilot_cache.py`
- Test: `tests/test_autopilot_cache.py`

**Interfaces:**
- Consumes: `tools.fundamentals.analyze` (injectable as `_analyze`).
- Produces: `get_fundamentals(ticker, today_iso, cache_path, _analyze=None) -> dict`. Cache file shape: `{"date": "<iso>", "tickers": {"<t>": <analyze-result>}}`. On a new date the cache resets. A cached ticker for today is returned without refetching.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autopilot_cache.py
import json
from tools.autopilot_cache import get_fundamentals


def test_first_call_fetches_and_writes(tmp_path):
    calls = []
    def fake(t):
        calls.append(t)
        return {"ticker": t, "summary": "ok"}
    p = tmp_path / "fund.json"
    out = get_fundamentals("NVDA", "2026-07-06", str(p), _analyze=fake)
    assert out["summary"] == "ok"
    assert calls == ["NVDA"]
    saved = json.loads(p.read_text())
    assert saved["date"] == "2026-07-06"
    assert saved["tickers"]["NVDA"]["summary"] == "ok"


def test_same_day_uses_cache(tmp_path):
    calls = []
    def fake(t):
        calls.append(t)
        return {"ticker": t}
    p = tmp_path / "fund.json"
    get_fundamentals("NVDA", "2026-07-06", str(p), _analyze=fake)
    get_fundamentals("NVDA", "2026-07-06", str(p), _analyze=fake)
    assert calls == ["NVDA"]   # second call served from cache


def test_new_day_resets_cache(tmp_path):
    calls = []
    def fake(t):
        calls.append(t)
        return {"ticker": t}
    p = tmp_path / "fund.json"
    get_fundamentals("NVDA", "2026-07-06", str(p), _analyze=fake)
    get_fundamentals("NVDA", "2026-07-07", str(p), _analyze=fake)
    assert calls == ["NVDA", "NVDA"]
    saved = json.loads(p.read_text())
    assert saved["date"] == "2026-07-07"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_autopilot_cache.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.autopilot_cache'`

- [ ] **Step 3: Write minimal implementation**

```python
# tools/autopilot_cache.py
"""Daily fundamentals cache for TRaid Autopilot.

Fundamentals are quarterly data — pointless to refetch every hour. Cache them
per NY date; a new date wipes the cache and refetches on demand.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _default_analyze(ticker):
    from tools.fundamentals import analyze
    return analyze(ticker)


def _load(cache_path, today_iso):
    try:
        with open(cache_path) as f:
            data = json.load(f)
        if data.get("date") == today_iso and isinstance(data.get("tickers"), dict):
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {"date": today_iso, "tickers": {}}


def get_fundamentals(ticker, today_iso, cache_path, _analyze=None):
    analyze = _analyze or _default_analyze
    data = _load(cache_path, today_iso)
    if ticker not in data["tickers"]:
        data["tickers"][ticker] = analyze(ticker)
        os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(data, f, indent=2)
    return data["tickers"][ticker]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_autopilot_cache.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add tools/autopilot_cache.py tests/test_autopilot_cache.py
git commit -m "feat(autopilot): daily fundamentals cache (fetch once per NY date)"
```

---

## Task 6: Status renderer

Pure formatting of the human-readable `status.txt`. No I/O, so it's fully testable.

**Files:**
- Create: `tools/autopilot_status.py`
- Test: `tests/test_autopilot_status.py`

**Interfaces:**
- Consumes: the `mark_to_market` result shape.
- Produces: `render_status(marked, brain_label, updated_str, next_run_str, last_moves, halted=False) -> str`. `marked` is a `mark_to_market` dict; `last_moves` is a list of preformatted strings (newest first).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autopilot_status.py
from tools.autopilot_status import render_status

MARKED = {
    "cash": 1020.11, "invested": 4194.19, "total_value": 5214.30,
    "pnl_abs": 214.30, "pnl_pct": 4.29,
    "positions": [
        {"ticker": "NVDA", "shares": 12, "avg_cost": 118.40, "price": 131.02,
         "value": 1572.24, "pnl_abs": 151.44, "pnl_pct": 10.66},
    ],
}


def test_render_contains_headline_numbers():
    s = render_status(MARKED, "Fable 5", "2026-07-06 15:00 ART",
                      "2026-07-06 16:00 ART", ["15:00  BUY 2 NVDA @ $131.02 — momentum"])
    assert "brain today: Fable 5" in s
    assert "$5,214.30" in s
    assert "+$214.30" in s and "+4.29%" in s
    assert "NVDA" in s and "12 sh" in s
    assert "15:00  BUY 2 NVDA @ $131.02 — momentum" in s
    assert "next run: 2026-07-06 16:00 ART" in s


def test_render_shows_down_arrow_and_halt():
    down = dict(MARKED, pnl_abs=-1300.0, pnl_pct=-26.0)
    s = render_status(down, "Opus 4.8", "u", "n", [], halted=True)
    assert "-$1,300.00" in s
    assert "HALTED" in s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_autopilot_status.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.autopilot_status'`

- [ ] **Step 3: Write minimal implementation**

```python
# tools/autopilot_status.py
"""Renders data/autopilot/status.txt — the file the user opens to check in."""


def _money(x):
    return f"${abs(x):,.2f}"


def _signed_money(x):
    return f"{'+' if x >= 0 else '-'}{_money(x)}"


def _arrow(x):
    return "▲" if x >= 0 else "▼"  # ▲ / ▼


def render_status(marked, brain_label, updated_str, next_run_str, last_moves, halted=False):
    lines = []
    header = f"TRaid Autopilot — paper       brain today: {brain_label}"
    if halted:
        header += "   [HALTED: down ≥ 25%, no new buys]"
    lines.append(header)
    lines.append(f"Updated: {updated_str}   (next run: {next_run_str})")
    lines.append("")
    lines.append(
        f"BALANCE   {_money(marked['total_value'])}    "
        f"{_arrow(marked['pnl_abs'])} {_signed_money(marked['pnl_abs'])}  "
        f"({'+' if marked['pnl_pct'] >= 0 else ''}{marked['pnl_pct']}%)   since $5,000 start"
    )
    lines.append(f"CASH      {_money(marked['cash'])}    INVESTED {_money(marked['invested'])}")
    lines.append("")
    lines.append("POSITIONS")
    if marked["positions"]:
        for p in marked["positions"]:
            lines.append(
                f"  {p['ticker']:<5} {p['shares']:>4} sh  @ {_money(p['avg_cost'])} avg   "
                f"now {_money(p['price'])}   {_arrow(p['pnl_pct'])} {p['pnl_pct']:+.1f}%   "
                f"{_money(p['value'])}"
            )
    else:
        lines.append("  (all cash — no open positions)")
    lines.append("")
    lines.append("LAST MOVES")
    if last_moves:
        lines.extend(f"  {m}" for m in last_moves)
    else:
        lines.append("  (none yet)")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_autopilot_status.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add tools/autopilot_status.py tests/test_autopilot_status.py
git commit -m "feat(autopilot): plain-text status.txt renderer"
```

---

## Task 7: Runner — `prepare` verb

Assembles the market snapshot the brain reads: market-open flag, today's model, marked account, and a compact per-ticker block (technicals + cached fundamentals + news). Network-touching pieces are injected so the test runs offline.

**Files:**
- Create: `tools/autopilot.py`
- Test: `tests/test_autopilot_prepare.py`

**Interfaces:**
- Consumes: `autopilot_broker`, `autopilot_clock`, `autopilot_cache.get_fundamentals`, `autopilot_news.headlines`, `tools.indicators.analyze`, `tools.market.quote`.
- Produces:
  - Module constants: `ACCOUNT_PATH`, `TRADES_PATH`, `STATUS_PATH`, `FUND_CACHE_PATH`, `WATCHLIST_PATH` (all under `data/autopilot/` except watchlist at root).
  - `load_watchlist(path=WATCHLIST_PATH) -> list[str]`
  - `build_snapshot(now_utc, watchlist, account, deps) -> dict` where `deps` is a dict of injectable callables `{"indicators","fundamentals","news","price"}`. Returns `{"as_of","market_open","brain_model","brain_label","account": <marked>, "tickers": {t: {"price","position","technicals","fundamentals","news"}}}`.
  - `cmd_prepare() -> dict` (real deps; prints JSON in `main`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autopilot_prepare.py
from datetime import datetime, timezone
from tools.autopilot_broker import new_account, apply_fill
from tools.autopilot import build_snapshot

OPEN_UTC = datetime(2026, 7, 6, 14, 0, tzinfo=timezone.utc)   # Mon 10:00 ET


def _deps():
    return {
        "indicators": lambda t: {"ticker": t, "confluence": {"summary": "mixed"},
                                 "indicators": {"rsi": {"value": 55}}},
        "fundamentals": lambda t: {"ticker": t, "valuation": {"peg": 1.2}, "summary": "solid"},
        "news": lambda t: [{"title": f"{t} up", "source": "X", "published": "", "url": ""}],
        "price": lambda t: 100.0,
    }


def test_snapshot_shape_and_brain():
    acct = apply_fill(new_account(5000.0), "buy", "NVDA", 2, 100.0)
    snap = build_snapshot(OPEN_UTC, ["NVDA", "META"], acct, _deps())
    assert snap["market_open"] is True
    assert snap["brain_model"] == "claude-fable-5"
    assert snap["brain_label"] == "Fable 5"
    assert snap["account"]["total_value"] == 5000.0
    assert set(snap["tickers"]) == {"NVDA", "META"}
    nvda = snap["tickers"]["NVDA"]
    assert nvda["price"] == 100.0
    assert nvda["position"] == 2
    assert nvda["fundamentals"]["valuation"]["peg"] == 1.2
    assert nvda["news"][0]["title"] == "NVDA up"


def test_snapshot_marks_closed_off_hours():
    after = datetime(2026, 7, 6, 21, 0, tzinfo=timezone.utc)  # 17:00 ET
    snap = build_snapshot(after, ["NVDA"], new_account(5000.0), _deps())
    assert snap["market_open"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_autopilot_prepare.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.autopilot'`

- [ ] **Step 3: Write minimal implementation**

```python
# tools/autopilot.py
"""TRaid Autopilot runner CLI.

Verbs:
  prepare              -> print a JSON market snapshot + today's brain model
  execute '<orders>'   -> validate orders through rails, fill, rewrite status.txt
  brain-model          -> print today's model id (for the run wrapper)

Money-logic lives in the pure modules (broker/rails/status); this file wires
them to live data and the filesystem.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.autopilot_broker import new_account, load_account, save_account, position_shares, mark_to_market
from tools.autopilot_clock import is_market_open, brain_model_for, brain_label
from tools.autopilot_cache import get_fundamentals
from tools.autopilot_news import headlines

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DIR = os.path.join(_ROOT, "data", "autopilot")
ACCOUNT_PATH = os.path.join(_DIR, "account.json")
TRADES_PATH = os.path.join(_DIR, "trades.jsonl")
STATUS_PATH = os.path.join(_DIR, "status.txt")
FUND_CACHE_PATH = os.path.join(_DIR, "fundamentals_cache.json")
WATCHLIST_PATH = os.path.join(_ROOT, "watchlist.json")
_NY = ZoneInfo("America/New_York")
_ART = ZoneInfo("America/Argentina/Buenos_Aires")


def load_watchlist(path=WATCHLIST_PATH):
    with open(path) as f:
        return json.load(f)


def _price_quote(ticker):
    from tools.market import quote
    q = quote(ticker)
    return q.get("price") if isinstance(q, dict) else None


def _indicators(ticker):
    from tools.indicators import analyze
    return analyze(ticker, period="6mo")


def build_snapshot(now_utc, watchlist, account, deps):
    ny_date = now_utc.astimezone(_NY).date()
    model = brain_model_for(ny_date)
    prices = {}
    tickers = {}
    for t in watchlist:
        price = deps["price"](t)
        prices[t] = price if price else 0.0
        tickers[t] = {
            "price": price,
            "position": position_shares(account, t),
            "technicals": deps["indicators"](t),
            "fundamentals": deps["fundamentals"](t),
            "news": deps["news"](t),
        }
    return {
        "as_of": now_utc.isoformat(),
        "market_open": is_market_open(now_utc),
        "brain_model": model,
        "brain_label": brain_label(model),
        "account": mark_to_market(account, prices),
        "tickers": tickers,
    }


def _load_or_create_account():
    if os.path.exists(ACCOUNT_PATH):
        return load_account(ACCOUNT_PATH)
    acct = new_account(5000.0)
    save_account(acct, ACCOUNT_PATH)
    return acct


def cmd_prepare():
    now = datetime.now(timezone.utc)
    watchlist = load_watchlist()
    account = _load_or_create_account()
    today_iso = now.astimezone(_NY).date().isoformat()
    deps = {
        "indicators": _indicators,
        "fundamentals": lambda t: get_fundamentals(t, today_iso, FUND_CACHE_PATH),
        "news": headlines,
        "price": _price_quote,
    }
    return build_snapshot(now, watchlist, account, deps)


def main(argv=None):
    p = argparse.ArgumentParser(description="TRaid Autopilot runner")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare")
    args = p.parse_args(argv)
    if args.cmd == "prepare":
        print(json.dumps(cmd_prepare(), indent=2, default=str))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_autopilot_prepare.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add tools/autopilot.py tests/test_autopilot_prepare.py
git commit -m "feat(autopilot): runner 'prepare' verb — market snapshot + brain selection"
```

---

## Task 8: Runner — `execute` + `brain-model` verbs

Validates proposed orders through the rails, fills survivors, appends the trade log, and rewrites `status.txt`. Rejected orders are logged, never filled.

**Files:**
- Modify: `tools/autopilot.py` (add `execute_orders`, `cmd_execute`, `cmd_brain_model`, extend `main`)
- Test: `tests/test_autopilot_execute.py`

**Interfaces:**
- Consumes: everything from Task 7 plus `autopilot_rails.is_halted`, `validate_order`; `autopilot_status.render_status`.
- Produces:
  - `execute_orders(orders, account, prices, watchlist, now_utc) -> (new_account, results)` where `results` is a list of `{"order","filled":bool,"reason","price"}`. Pure except it takes explicit prices; used by `cmd_execute`.
  - `_next_run_art(now_utc) -> str` and `_fmt_art(now_utc) -> str` (display helpers).
  - `cmd_execute(orders_json) -> dict`, `cmd_brain_model() -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autopilot_execute.py
from datetime import datetime, timezone
from tools.autopilot_broker import new_account
from tools.autopilot import execute_orders

OPEN_UTC = datetime(2026, 7, 6, 14, 0, tzinfo=timezone.utc)
WL = ["NVDA", "META"]
PRICES = {"NVDA": 100.0, "META": 200.0}


def test_valid_buy_fills_and_updates_cash():
    orders = [{"side": "buy", "ticker": "NVDA", "shares": 3}]
    acct, results = execute_orders(orders, new_account(5000.0), PRICES, WL, OPEN_UTC)
    assert results[0]["filled"] is True
    assert acct["cash"] == 4700.0


def test_off_watchlist_rejected_not_filled():
    orders = [{"side": "buy", "ticker": "TSLA", "shares": 1}]
    acct, results = execute_orders(orders, new_account(5000.0), {"TSLA": 100.0}, WL, OPEN_UTC)
    assert results[0]["filled"] is False
    assert "watchlist" in results[0]["reason"].lower()
    assert acct["cash"] == 5000.0


def test_over_40pct_rejected():
    orders = [{"side": "buy", "ticker": "NVDA", "shares": 30}]  # $3000 of $5000 = 60%
    acct, results = execute_orders(orders, new_account(5000.0), PRICES, WL, OPEN_UTC)
    assert results[0]["filled"] is False
    assert acct["cash"] == 5000.0


def test_market_closed_fills_nothing():
    closed = datetime(2026, 7, 6, 21, 0, tzinfo=timezone.utc)
    orders = [{"side": "buy", "ticker": "NVDA", "shares": 1}]
    acct, results = execute_orders(orders, new_account(5000.0), PRICES, WL, closed)
    assert results[0]["filled"] is False
    assert acct["cash"] == 5000.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_autopilot_execute.py -v`
Expected: FAIL with `ImportError: cannot import name 'execute_orders'`

- [ ] **Step 3: Write minimal implementation**

Add to `tools/autopilot.py` (imports near the top, functions before `main`):

```python
# --- add to the import block ---
from tools.autopilot_rails import is_halted, validate_order
from tools.autopilot_status import render_status
```

```python
# --- add above main() ---
def _fmt_art(now_utc):
    return now_utc.astimezone(_ART).strftime("%Y-%m-%d %H:%M ART")


def _next_run_art(now_utc):
    return (now_utc + timedelta(hours=1)).astimezone(_ART).strftime("%Y-%m-%d %H:%M ART")


def execute_orders(orders, account, prices, watchlist, now_utc):
    market_open = is_market_open(now_utc)
    halted = is_halted(account, prices)
    acct = account
    results = []
    for order in orders:
        ok, reason = validate_order(order, acct, prices, watchlist, market_open, halted)
        price = prices.get(order.get("ticker"))
        if ok:
            from tools.autopilot_broker import apply_fill
            acct = apply_fill(acct, order["side"], order["ticker"], order["shares"], price)
            halted = is_halted(acct, prices)  # re-check after each fill
        results.append({"order": order, "filled": ok, "reason": reason, "price": price})
    return acct, results


def _append_trades(results, now_utc):
    os.makedirs(_DIR, exist_ok=True)
    stamp = now_utc.astimezone(_ART).strftime("%H:%M")
    moves = []
    with open(TRADES_PATH, "a") as f:
        for r in results:
            o = r["order"]
            rec = {"at": now_utc.isoformat(), "side": o.get("side"), "ticker": o.get("ticker"),
                   "shares": o.get("shares"), "price": r["price"], "filled": r["filled"],
                   "reason": r.get("order", {}).get("reason", ""), "rail": r["reason"]}
            f.write(json.dumps(rec) + "\n")
            if r["filled"]:
                why = o.get("reason", "")
                moves.append(f"{stamp}  {o['side'].upper()} {o['shares']} {o['ticker']} @ ${r['price']:.2f}"
                             + (f" — {why}" if why else ""))
    if not any(r["filled"] for r in results):
        moves.append(f"{stamp}  HOLD everything")
    return moves


def cmd_execute(orders_json):
    orders = json.loads(orders_json) if isinstance(orders_json, str) else orders_json
    now = datetime.now(timezone.utc)
    account = _load_or_create_account()
    watchlist = load_watchlist()
    prices = {}
    for t in set(watchlist) | {o.get("ticker") for o in orders}:
        prices[t] = _price_quote(t) or 0.0
    acct, results = execute_orders(orders, account, prices, watchlist, now)
    acct["halted"] = is_halted(acct, prices)
    save_account(acct, ACCOUNT_PATH)
    moves = _append_trades(results, now)
    marked = mark_to_market(acct, prices)
    model = brain_model_for(now.astimezone(_NY).date())
    status = render_status(marked, brain_label(model), _fmt_art(now), _next_run_art(now),
                           list(reversed(moves)), halted=acct["halted"])
    os.makedirs(_DIR, exist_ok=True)
    with open(STATUS_PATH, "w") as f:
        f.write(status)
    return {"filled": sum(1 for r in results if r["filled"]), "results": results}


def cmd_brain_model():
    return brain_model_for(datetime.now(timezone.utc).astimezone(_NY).date())
```

Replace the body of `main()` with:

```python
def main(argv=None):
    p = argparse.ArgumentParser(description="TRaid Autopilot runner")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare")
    ex = sub.add_parser("execute")
    ex.add_argument("orders", help="JSON list of orders")
    sub.add_parser("brain-model")
    args = p.parse_args(argv)
    if args.cmd == "prepare":
        print(json.dumps(cmd_prepare(), indent=2, default=str))
    elif args.cmd == "execute":
        print(json.dumps(cmd_execute(args.orders), indent=2, default=str))
    elif args.cmd == "brain-model":
        print(cmd_brain_model())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_autopilot_execute.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Run the full suite**

Run: `./.venv/bin/pytest -q`
Expected: PASS (all prior tests + the new autopilot tests)

- [ ] **Step 6: Commit**

```bash
git add tools/autopilot.py tests/test_autopilot_execute.py
git commit -m "feat(autopilot): runner 'execute'/'brain-model' — rails-gated fills + status write"
```

---

## Task 9: Scheduling, orchestration wiring, and docs

The glue that runs it hands-off: the headless-Claude orchestration prompt, a `caffeinate` wrapper whose `claude -p` model IS the brain, an hourly `launchd` job, gitignore, and a README section. No unit test — ends with a manual smoke test.

**Files:**
- Create: `tools/autopilot_prompt.md` (instructions for the headless brain session)
- Create: `scripts/autopilot-run.sh`
- Create: `scripts/com.traid.autopilot.plist`
- Modify: `.gitignore` (add `data/autopilot/`)
- Modify: `README.md` (add an Autopilot section)

- [ ] **Step 1: Write the orchestration prompt**

```markdown
<!-- tools/autopilot_prompt.md -->
# TRaid Autopilot — run instructions (you are today's brain)

You are running headless to manage a **paper** ($5,000 simulated) portfolio.
This is a decision-support experiment, NOT financial advice. No real money moves.

Do exactly this, then stop:

1. Run: `./.venv/bin/python tools/autopilot.py prepare`
   It prints JSON: `market_open`, `brain_label`, the marked `account`, and per-ticker
   `price` / `position` / `technicals` / `fundamentals` / `news`.
2. If `market_open` is false, STOP — do nothing (the status file is refreshed on execute runs only).
3. Otherwise decide **long-only** orders on watchlist names using the snapshot.
   Weigh fundamentals (PEG/valuation/growth) first, then technicals (RSI/MACD/trend/confluence),
   then news as a light hint. Sizing is yours, but the code enforces: no leverage, <=40% per
   name, no shorting, halt at -25%. Day trading (same-day buy+sell) is allowed.
   Prefer inaction to a weak edge — HOLD is a valid whole answer.
4. Build a JSON array of orders. Each: `{"side":"buy"|"sell","ticker":"NVDA","shares":N,"reason":"one short line"}`.
   For no trades, use `[]`.
5. Run: `./.venv/bin/python tools/autopilot.py execute '<that JSON>'`
6. Report one line: how many filled and the new balance. Stop.
```

- [ ] **Step 2: Write the run wrapper**

```bash
# scripts/autopilot-run.sh
#!/usr/bin/env bash
# Hourly TRaid Autopilot run. The headless `claude` session's own --model IS
# the brain (Fable through Jul 7, then Opus). caffeinate keeps the Mac awake
# for the run. All paper — no real orders.
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL="$(./.venv/bin/python tools/autopilot.py brain-model)"
PROMPT="$(cat tools/autopilot_prompt.md)"

# -i prevents idle sleep during the run; claude -p runs headless under the subscription.
caffeinate -i claude -p --model "$MODEL" "$PROMPT" >> data/autopilot/run.log 2>&1
```

- [ ] **Step 3: Make it executable and smoke-test the wrapper's model pick**

Run:
```bash
chmod +x scripts/autopilot-run.sh
./.venv/bin/python tools/autopilot.py brain-model
```
Expected: prints `claude-fable-5` (today is before Jul 8) — confirms the wrapper will select Fable.

- [ ] **Step 4: Write the hourly launchd job**

```xml
<!-- scripts/com.traid.autopilot.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<!--
  TRaid Autopilot — hourly (macOS launchd). Fires every hour; the bot's own
  market-open guard decides whether a given hour trades or no-ops, so DST and
  the exact clock never need tuning. Wide window covers US hours from Argentina.

  Install:
    cp scripts/com.traid.autopilot.plist ~/Library/LaunchAgents/
    launchctl load ~/Library/LaunchAgents/com.traid.autopilot.plist
  Remove:
    launchctl unload ~/Library/LaunchAgents/com.traid.autopilot.plist
-->
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.traid.autopilot</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/martinmana/Documents/Projects/TRaid/scripts/autopilot-run.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/martinmana/Documents/Projects/TRaid</string>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Minute</key><integer>5</integer></dict>
  </array>
  <key>StandardOutPath</key>
  <string>/Users/martinmana/Documents/Projects/TRaid/data/autopilot/launchd.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/martinmana/Documents/Projects/TRaid/data/autopilot/launchd.log</string>
</dict>
</plist>
```

Note: a single `<dict>` with only `Minute` fires once per hour at :05, every hour, every day. The market-open guard handles weekends/holidays/off-hours.

- [ ] **Step 5: Gitignore the runtime data**

Add to `.gitignore` under the personal-data section:

```
# Autopilot runtime state (local paper trading — never commit)
data/autopilot/
```

- [ ] **Step 6: Add the README section**

Append to `README.md`:

```markdown
## TRaid Autopilot (paper) — hands-off local experiment

A fully local paper-trading bot: every US-market hour, an AI brain (Fable 5, then
Opus 4.8) proposes long-only trades on your watchlist within **code-enforced rails**
(no leverage, ≤40% per name, no shorting, −25% circuit breaker). $5,000 of Monopoly
money in a JSON file — no broker, no keys, nothing leaves your Mac. **Decision-support,
not financial advice.**

**Check on it:** open `data/autopilot/status.txt` — balance, ± % and $, positions, moves.

**Run once by hand:**
```bash
./scripts/autopilot-run.sh          # one full hourly cycle (needs the `claude` CLI)
# or step through it:
./.venv/bin/python tools/autopilot.py prepare
./.venv/bin/python tools/autopilot.py execute '[]'   # '[]' = hold everything
```

**Schedule it hourly (macOS):**
```bash
cp scripts/com.traid.autopilot.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.traid.autopilot.plist
```
Keep your Mac awake during US market hours; `caffeinate` covers the firing minute.
```

- [ ] **Step 7: Manual smoke test (one real cycle)**

Run:
```bash
./.venv/bin/python tools/autopilot.py prepare | head -40
./.venv/bin/python tools/autopilot.py execute '[]'
cat data/autopilot/status.txt
```
Expected: `prepare` prints valid JSON with `market_open`, `brain_model`, `account`, and
per-ticker blocks; `execute '[]'` writes `data/autopilot/status.txt` showing $5,000.00
balance, all cash, no positions, "HOLD everything". (If run outside US hours, `market_open`
is false and that's correct.)

- [ ] **Step 8: Commit**

```bash
git add tools/autopilot_prompt.md scripts/autopilot-run.sh scripts/com.traid.autopilot.plist .gitignore README.md
git commit -m "feat(autopilot): hourly launchd job, headless-brain run wrapper, docs"
```

---

## Self-Review

**1. Spec coverage:**
- Local paper broker (no Alpaca) → Task 1. ✅
- Rails in code (long-only, no leverage, watchlist, 40%, −25% breaker, market-open) → Task 2. ✅
- Hourly + market-open guard + DST-proof → Task 3 (clock) + Task 9 (hourly plist). ✅
- Brain by date (Fable→Opus), free under subscription → Task 3 selector + Task 9 wrapper (`claude -p --model`). ✅
- News (yfinance headlines) → Task 4. ✅
- Daily-cached fundamentals → Task 5. ✅
- Technical + fundamental "good TRaid data" in the snapshot → Task 7 (`build_snapshot` reuses `indicators.analyze` + cache + news). ✅
- `status.txt` (balance, ±%/$, positions, moves) → Task 6 + written in Task 8. ✅
- Fully autonomous, no approval, no Telegram/Vercel/GitHub → orchestration is prepare→decide→execute only (Task 9). ✅
- $5k / watchlist whitelist / 5-day window → constants + `load_watchlist` + `brain_model_for` window. ✅
- Trade log, idempotent-ish, graceful degradation → `trades.jsonl` (Task 8), per-ticker error swallowing in news/quote. ✅

**2. Placeholder scan:** No TBD/TODO; every code step is complete and runnable. ✅

**3. Type consistency:** `mark_to_market` result keys (`total_value`, `pnl_abs`, `pnl_pct`, `positions[].value/pnl_pct`) are consumed identically in rails (Task 2), status (Task 6), and execute (Task 8). `validate_order` signature `(order, account, prices, watchlist, market_open, halted)` matches its call site in `execute_orders` (Task 8). `order` dict shape `{"side","ticker","shares","reason?"}` is consistent across rails, execute, and the prompt. `build_snapshot(now_utc, watchlist, account, deps)` matches its test and `cmd_prepare`. ✅

Note carried to execution: Task 8 edits `main()` and the import block created in Task 7 — apply those edits in-place rather than appending duplicates.
