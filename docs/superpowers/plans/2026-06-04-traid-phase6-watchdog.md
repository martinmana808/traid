# TRaid Phase 6 — Proactive Watchdog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use `- [ ]` checkboxes.

**Goal:** A scheduled watchdog that runs without you opening Claude Code, checks your portfolio + predictions for things worth knowing, and pushes a concise alert to your **iPhone (Telegram)** and **Mac (native notification)** — quiet when nothing matters.

**Architecture:** `tools/watchdog.py`. The alert RULES are a pure, unit-tested function (`evaluate_alerts`) — the "signal vs noise" core. Data gathering reuses existing tools (portfolio.json, `market.quote`, `scorecard.run`). Delivery = Telegram Bot API (HTTP) + macOS `osascript`. State (`data/watchdog_state.json`, gitignored) dedupes so it never re-nags. Secrets in `.env` (gitignored). Scheduled via a macOS `launchd` plist.

**Alert rules (what's worth interrupting you for):**
1. A holding moved ≥ `move_pct` (default 7%) on the day.
2. A logged prediction has **matured** (time to verify) — alerted once per prediction id.
3. Foreign-share cost approaches the **NZ$50k FIF threshold** (warn at $45k).
4. (quiet otherwise — no daily "all clear" spam unless `--digest`.)

**Tech Stack:** Python 3, yfinance, pytest. No new deps (Telegram + Mac use stdlib `urllib`/`subprocess`).

---

## File Structure
- `tools/watchdog.py` — pure `evaluate_alerts` + data gathering + Telegram/Mac delivery + CLI
- `tests/test_watchdog.py` — unit tests for the alert rules + dedupe
- `scripts/com.traid.watchdog.plist` — launchd schedule template
- `.env.example` — secret placeholders (real `.env` is gitignored)
- `README.md` — document; Telegram setup guide; mark Phase 6 done

---

## Task 1: Alert rules (TDD)

**Files:** Create `tools/watchdog.py`, `tests/test_watchdog.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_watchdog.py
from tools.watchdog import evaluate_alerts


def base_cfg():
    return {"move_pct": 7, "fif_warn": 45000}


def test_big_move_triggers_alert():
    holdings = [{"ticker": "NVDA"}]
    quotes = {"NVDA": {"price": 200.0, "change_pct": -9.0}}
    alerts, _ = evaluate_alerts(holdings, quotes, [], None, {}, base_cfg())
    assert any("NVDA" in a["message"] for a in alerts)


def test_small_move_no_alert():
    holdings = [{"ticker": "NVDA"}]
    quotes = {"NVDA": {"price": 200.0, "change_pct": 2.0}}
    alerts, _ = evaluate_alerts(holdings, quotes, [], None, {}, base_cfg())
    assert alerts == []


def test_matured_prediction_alerts_once():
    matured = [{"id": "2026-06-03-001", "call": "buy", "ticker": "VT"}]
    alerts, state = evaluate_alerts([], {}, matured, None, {}, base_cfg())
    assert any("2026-06-03-001" in a["message"] for a in alerts)
    # second run with returned state -> no repeat
    alerts2, _ = evaluate_alerts([], {}, matured, None, state, base_cfg())
    assert alerts2 == []


def test_fif_threshold_warns_only_when_near():
    a1, _ = evaluate_alerts([], {}, [], 4000.0, {}, base_cfg())
    assert a1 == []
    a2, _ = evaluate_alerts([], {}, [], 46000.0, {}, base_cfg())
    assert any("FIF" in a["message"] or "50k" in a["message"] for a in a2)
```

- [ ] **Step 2: Run — expect fail** `./.venv/bin/pytest tests/test_watchdog.py -v`
- [ ] **Step 3: Implement `tools/watchdog.py`** (pure rules + gathering + delivery + CLI — full code in repo).
- [ ] **Step 4: Run — expect pass** `./.venv/bin/pytest tests/test_watchdog.py -v`
- [ ] **Step 5: Smoke test** `./.venv/bin/python tools/watchdog.py --check --dry-run` → prints alerts it *would* send (no secrets needed).
- [ ] **Step 6: Commit** `git add tools/watchdog.py tests/test_watchdog.py && git commit -m "feat: watchdog alert rules + delivery (Telegram + Mac)"`

---

## Task 2: launchd schedule + .env.example + README/setup

- [ ] **Step 1:** Create `scripts/com.traid.watchdog.plist` (runs weekdays 9am NZT), `.env.example` (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, WATCHDOG_MOVE_PCT).
- [ ] **Step 2:** README: Telegram bot setup (BotFather → token → `--get-chat-id`), `--test`, and how to load the launchd job. Mark Phase 6 done.
- [ ] **Step 3:** `./.venv/bin/pytest -q` → all pass.
- [ ] **Step 4: Commit** `git add scripts/ .env.example README.md && git commit -m "feat: watchdog scheduling + setup docs"`

---

## Self-Review
- Delivery to iPhone (Telegram) + Mac (native). ✓
- Alert rules pure + tested incl. dedupe (no re-nagging). ✓
- Quiet by default (no all-clear spam). ✓
- Secrets in gitignored .env; state gitignored. ✓
- Scheduling via launchd template. ✓
