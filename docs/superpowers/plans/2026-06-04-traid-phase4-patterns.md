# TRaid Phase 4 — Pattern Recognition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use `- [ ]` checkboxes.

**Goal:** Detect candlestick patterns (with a 0–100 match score) and basic price structure (support/resistance, swing-trend) from OHLCV, and surface them to the analyst as *low-weight context* — never as predictors.

**Architecture:** A new `tools/patterns.py`. Pure detection functions (operate on lists of OHLC bars, fully unit-tested with hand-crafted candles) + an `analyze()` that fetches recent history (reusing `tools.market`), scans the latest candles, and returns detected patterns with scores, readings, and a structure summary. Honesty is built in: every output carries a "patterns are weak/contested — context only" note.

**Honest scope:** Candlestick patterns done properly (the reliable, rule-based part). Basic structure = swing-pivot detection + nearest support/resistance + are-swings-rising/falling. **Out of scope (deliberately):** named chart formations (Head & Shoulders, flags, triangles) — fuzzy, error-prone, deferred rather than faked.

**Tech Stack:** Python 3, yfinance, pytest. (No new deps.)

**Patterns implemented:** Doji, Hammer, Inverted Hammer, Shooting Star, Bullish Engulfing, Bearish Engulfing, Morning Star, Evening Star.

---

## File Structure
- `tools/patterns.py` — candlestick detectors (pure) + pivots/structure + `analyze()` + CLI
- `tests/test_patterns.py` — unit tests on hand-crafted candles
- `.claude/skills/traid-analyst/SKILL.md` — surface patterns as low-weight context in timing step
- `README.md` — document the tool; mark Phase 4 done; list Phase 5/6 roadmap

---

## Task 1: Candlestick detectors + structure (TDD)

**Files:** Create `tools/patterns.py`, `tests/test_patterns.py`

**Helper conventions** (a "bar" is a dict with float `open/high/low/close`):
- `body = abs(close-open)`, `rng = high-low`
- `upper_shadow = high - max(open,close)`, `lower_shadow = min(open,close) - low`
- Each detector returns an int score 0–100 (0 = absent). Threshold for "present" = 50.

- [ ] **Step 1: Failing tests**

```python
# tests/test_patterns.py
from tools.patterns import (
    doji, hammer, shooting_star, bullish_engulfing, bearish_engulfing,
    morning_star, evening_star, find_pivots,
)


def bar(o, h, l, c):
    return {"open": o, "high": h, "low": l, "close": c}


def test_doji_detected_on_tiny_body():
    # open ~ close, real range -> doji
    assert doji([bar(100, 105, 95, 100.2)]) >= 50


def test_doji_absent_on_big_body():
    assert doji([bar(100, 106, 99, 105)]) == 0


def test_hammer_long_lower_shadow():
    # small body up top, long lower shadow, tiny upper shadow
    assert hammer([bar(100, 100.5, 92, 100)]) >= 50


def test_hammer_absent_when_no_lower_shadow():
    assert hammer([bar(100, 106, 99.8, 105)]) == 0


def test_shooting_star_long_upper_shadow():
    assert shooting_star([bar(100, 108, 99.7, 100)]) >= 50


def test_bullish_engulfing():
    prev = bar(100, 100.5, 96, 97)      # red
    cur = bar(96.5, 102, 96, 101)       # green, body engulfs prev body
    assert bullish_engulfing([prev, cur]) >= 50


def test_bearish_engulfing():
    prev = bar(100, 104, 99.5, 103)     # green
    cur = bar(103.5, 104, 98, 99)       # red, engulfs
    assert bearish_engulfing([prev, cur]) >= 50


def test_engulfing_absent_when_inside():
    prev = bar(100, 105, 95, 104)
    cur = bar(101, 103, 100, 102)       # inside prev body -> not engulfing
    assert bullish_engulfing([prev, cur]) == 0


def test_morning_star_bullish_reversal():
    c1 = bar(100, 100.5, 90, 91)        # big red
    c2 = bar(90, 91, 88, 89.5)          # small body
    c3 = bar(90, 98, 89.5, 97)          # big green into c1 body
    assert morning_star([c1, c2, c3]) >= 50


def test_evening_star_bearish_reversal():
    c1 = bar(90, 100, 89.5, 99)         # big green
    c2 = bar(99, 101, 98.5, 100)        # small body
    c3 = bar(99, 99.5, 91, 92)          # big red into c1 body
    assert evening_star([c1, c2, c3]) >= 50


def test_find_pivots_zigzag():
    highs = [1, 2, 3, 2, 1, 2, 3, 4, 3, 2]
    lows = [h - 1 for h in highs]
    piv = find_pivots(highs, lows, window=1)
    assert any(p["kind"] == "high" for p in piv)
    assert any(p["kind"] == "low" for p in piv)
```

- [ ] **Step 2: Run — expect fail** `./.venv/bin/pytest tests/test_patterns.py -v`

- [ ] **Step 3: Implement `tools/patterns.py`** (detectors + scoring + pivots + analyze + CLI — full code in repo file).

- [ ] **Step 4: Run — expect pass** `./.venv/bin/pytest tests/test_patterns.py -v`

- [ ] **Step 5: Live smoke test** `./.venv/bin/python tools/patterns.py NVDA` → JSON with any recent candlestick patterns + structure + honesty note.

- [ ] **Step 6: Commit** `git add tools/patterns.py tests/test_patterns.py && git commit -m "feat: candlestick pattern detection with match scores + structure"`

---

## Task 2: Wire patterns into the analyst skill

- [ ] **Step 1:** In `SKILL.md` timing step, add: optionally run `./.venv/bin/python tools/patterns.py <TICKER>`; mention any detected candlestick patterns as **what a chart-reader would note — low weight, contested predictive power, context only.** Never let a pattern override fundamentals/risk.
- [ ] **Step 2: Commit** `git add .claude/skills/traid-analyst/SKILL.md && git commit -m "feat: analyst surfaces candlestick patterns as low-weight context"`

---

## Task 3: README + full suite

- [ ] **Step 1:** Add `patterns.py` usage to `README.md`; mark Phase 4 done; list Phase 5 (Deep Fundamentals) & Phase 6 (Proactive Watchdog).
- [ ] **Step 2:** `./.venv/bin/pytest -q` → all pass.
- [ ] **Step 3: Commit** `git add README.md && git commit -m "docs: document patterns; roadmap Phase 5/6"`

---

## Roadmap (committed direction)
- **Phase 5 — Deep Fundamentals:** revenue/earnings growth, margins, forward P/E, PEG, debt, free cash flow — data-backed "good business at a fair price."
- **Phase 6 — Proactive Watchdog (THE GOAT):** scheduled portfolio check-ins — big moves, overbought/oversold, predictions due for verification — pushed to Martin instead of asked.

## Self-Review
- Candlestick patterns with 0–100 score (delivers the honest "similarity score"). ✓
- Structure via pivots + support/resistance. ✓
- Chart-formation naming deliberately deferred (honesty). ✓
- Efficacy caveat baked into output + skill. ✓
- Pure detectors unit-tested on crafted candles; live fetch smoke-tested. ✓
