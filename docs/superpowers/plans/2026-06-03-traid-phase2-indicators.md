# TRaid Phase 2 — Technical Indicators Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use `- [ ]` checkboxes.

**Goal:** Add a technical-indicator engine so TRaid can factor momentum, trend, and volatility into timing/swing recommendations — computed values *plus* plain-English readings, weighed as confluence, never as blind buy/sell triggers.

**Architecture:** A new `tools/indicators.py`. Pure indicator functions (operate on price lists/Series, fully unit-tested) + an `analyze()` that fetches history (reusing `tools.market`), computes the full suite, and emits JSON with values, per-indicator readings, and a confluence tally. Computation is done by hand with pandas/numpy (already installed via yfinance — no fragile TA dependency). RSI/ATR use **Wilder's smoothing (RMA)** to match TradingView.

**Tech Stack:** Python 3, pandas, numpy, yfinance, pytest.

**Indicator suite (user chose "full suite"):** RSI(14), MACD(12/26/9), Bollinger(20, 2σ), SMA 50 & 200 (trend + golden/death cross), Volume trend (vs 20-day avg), ATR(14), Stochastic(14/3).

**Design note (author = executor, same session):** Implementation code below is the source of truth; tests are written first and must fail before implementation (TDD).

---

## File Structure
- `tools/indicators.py` — indicator math (pure) + `analyze()` + CLI
- `tests/test_indicators.py` — unit tests for the pure functions + confluence tally
- `requirements.txt` — add explicit `pandas`, `numpy`
- `.claude/skills/traid-analyst/SKILL.md` — add indicator step to procedure
- `README.md` — document the new tool

---

## Task 1: Pin pandas/numpy

- [ ] **Step 1:** Append to `requirements.txt`:
```
pandas>=2.0
numpy>=1.24
```
- [ ] **Step 2:** Commit: `git add requirements.txt && git commit -m "chore: pin pandas/numpy for indicators"`

---

## Task 2: Indicator math (TDD)

**Files:** Create `tools/indicators.py`, `tests/test_indicators.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_indicators.py
import pandas as pd
from tools.indicators import (
    rsi, macd, bollinger, sma, atr, stochastic, volume_trend, confluence,
)


def last(series):
    return float(series.dropna().iloc[-1])


def test_sma_exact():
    assert last(sma([1, 2, 3, 4, 5], 5)) == 3.0


def test_rsi_monotonic_up_is_100():
    assert last(rsi(list(range(1, 40)), 14)) == 100.0


def test_rsi_monotonic_down_is_0():
    assert last(rsi(list(range(40, 1, -1)), 14)) == 0.0


def test_rsi_flat_is_50():
    assert last(rsi([10.0] * 40, 14)) == 50.0


def test_macd_constant_series_is_zero():
    macd_line, signal_line, hist = macd([5.0] * 60)
    assert abs(last(macd_line)) < 1e-9
    assert abs(last(hist)) < 1e-9


def test_bollinger_middle_equals_sma():
    closes = [float(x) for x in range(1, 41)]
    upper, mid, lower = bollinger(closes, 20, 2)
    assert last(mid) == last(sma(closes, 20))
    assert last(upper) > last(mid) > last(lower)


def test_stochastic_close_at_high_is_100():
    highs = [10.0] * 20
    lows = [5.0] * 20
    closes = [6.0] * 19 + [10.0]  # last close == period high
    k, d = stochastic(highs, lows, closes, 14, 3)
    assert last(k) == 100.0


def test_stochastic_close_at_low_is_0():
    highs = [10.0] * 20
    lows = [5.0] * 20
    closes = [6.0] * 19 + [5.0]  # last close == period low
    k, d = stochastic(highs, lows, closes, 14, 3)
    assert last(k) == 0.0


def test_atr_constant_range():
    # high-low always 2, no gaps -> ATR converges to 2
    highs = [12.0] * 30
    lows = [10.0] * 30
    closes = [11.0] * 30
    assert abs(last(atr(highs, lows, closes, 14)) - 2.0) < 1e-6


def test_volume_trend_constant_is_one():
    assert abs(last(volume_trend([1000.0] * 30, 20)) - 1.0) < 1e-9


def test_confluence_tally():
    signals = ["bullish", "bullish", "bearish", "neutral"]
    out = confluence(signals)
    assert out["bullish"] == 2 and out["bearish"] == 1 and out["neutral"] == 1
    assert "not a trade" in out["note"].lower()
```

- [ ] **Step 2: Run — expect fail** `./.venv/bin/pytest tests/test_indicators.py -v` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement `tools/indicators.py`** (pure functions + readings + analyze + CLI — full code, see repository file).

- [ ] **Step 4: Run — expect pass** `./.venv/bin/pytest tests/test_indicators.py -v` → all pass.

- [ ] **Step 5: Live smoke test** on a real ticker:
`./.venv/bin/python tools/indicators.py NVDA` → JSON with rsi/macd/bollinger/trend/atr/stochastic/volume + confluence.

- [ ] **Step 6: Commit** `git add tools/indicators.py tests/test_indicators.py && git commit -m "feat: technical indicator engine (RSI/MACD/Bollinger/MA/ATR/stoch/vol)"`

---

## Task 3: Wire indicators into the analyst skill

- [ ] **Step 1:** Insert into `SKILL.md` operating procedure, after the live-data step: a sub-step instructing the analyst to run `tools/indicators.py <TICKER>` for any timing/entry/swing judgement, present the readings, weigh them as confluence, and explicitly note that for long-term core decisions indicators are secondary to diversification/valuation/risk.
- [ ] **Step 2: Commit** `git add .claude/skills/traid-analyst/SKILL.md && git commit -m "feat: analyst uses indicators as confluence for timing"`

---

## Task 4: README + full suite

- [ ] **Step 1:** Add an indicators example to `README.md`.
- [ ] **Step 2:** Run `./.venv/bin/pytest -q` → all pass.
- [ ] **Step 3: Commit** `git add README.md && git commit -m "docs: document indicators tool"`

---

## Self-Review
- Suite covers user's "full suite" choice: RSI, MACD, Bollinger, SMA50/200, volume, ATR, stochastic. ✓
- Wilder smoothing for RSI/ATR (TradingView parity). ✓
- Readings + confluence are descriptive, explicitly "not a trade trigger." ✓
- Pure functions unit-tested with invariant/exact cases; live fetch smoke-tested. ✓
