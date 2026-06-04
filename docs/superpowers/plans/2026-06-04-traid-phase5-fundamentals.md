# TRaid Phase 5 — Deep Fundamentals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use `- [ ]` checkboxes.

**Goal:** Give TRaid real fundamentals — valuation (P/E, forward P/E, PEG), growth (revenue/earnings), profitability (margins, ROE), and financial health (debt, free cash flow) — with plain-English readings, so it judges *"good business at a fair price?"* with data instead of guesswork.

**Architecture:** A new `tools/fundamentals.py`. Pure classifier functions (PEG, valuation/growth/margin/health buckets) are unit-tested; `analyze()` pulls yfinance `.info` and assembles a structured report with readings + an honest summary. No new deps.

**Honesty:** Uses latest available YoY figures from yfinance — not a hand-audited multi-year model. Thresholds are rough heuristics, stated as such. Says "no P/E" for unprofitable names rather than inventing one.

**Tech Stack:** Python 3, yfinance, pytest.

---

## File Structure
- `tools/fundamentals.py` — pure classifiers + `analyze()` + CLI
- `tests/test_fundamentals.py` — unit tests for classifiers
- `.claude/skills/traid-analyst/SKILL.md` — pull fundamentals for any buy/valuation judgement
- `README.md` — document; mark Phase 5 done

---

## Task 1: Pure classifiers (TDD)

**Files:** Create `tools/fundamentals.py`, `tests/test_fundamentals.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_fundamentals.py
from tools.fundamentals import (
    compute_peg, classify_pe, classify_growth, classify_margin, classify_health,
)


def test_compute_peg_basic():
    assert compute_peg(30, 30) == 1.0


def test_compute_peg_none_without_growth():
    assert compute_peg(33, None) is None
    assert compute_peg(33, 0) is None
    assert compute_peg(33, -5) is None


def test_compute_peg_none_without_pe():
    assert compute_peg(None, 20) is None


def test_classify_pe_buckets():
    assert classify_pe(None)[0] == "n/a"
    assert classify_pe(12)[0] == "low"
    assert classify_pe(20)[0] == "moderate"
    assert classify_pe(33)[0] == "elevated"
    assert classify_pe(120)[0] == "high"


def test_classify_growth_buckets():
    assert classify_growth(None)[0] == "n/a"
    assert classify_growth(-3)[0] == "shrinking"
    assert classify_growth(3)[0] == "slow"
    assert classify_growth(12)[0] == "solid"
    assert classify_growth(40)[0] == "strong"


def test_classify_margin_buckets():
    assert classify_margin(None)[0] == "n/a"
    assert classify_margin(-5)[0] == "unprofitable"
    assert classify_margin(3)[0] == "thin"
    assert classify_margin(12)[0] == "healthy"
    assert classify_margin(35)[0] == "high"


def test_classify_health_buckets():
    assert classify_health(None)[0] == "n/a"
    assert classify_health(0.3)[0] == "low debt"
    assert classify_health(1.0)[0] == "moderate debt"
    assert classify_health(3.0)[0] == "high debt"
```

- [ ] **Step 2: Run — expect fail** `./.venv/bin/pytest tests/test_fundamentals.py -v`
- [ ] **Step 3: Implement `tools/fundamentals.py`** (classifiers + analyze + CLI — full code in repo file).
- [ ] **Step 4: Run — expect pass** `./.venv/bin/pytest tests/test_fundamentals.py -v`
- [ ] **Step 5: Live smoke test** `./.venv/bin/python tools/fundamentals.py NVDA` → valuation/growth/profitability/health + PEG + summary.
- [ ] **Step 6: Commit** `git add tools/fundamentals.py tests/test_fundamentals.py && git commit -m "feat: deep fundamentals (valuation/growth/profitability/health + PEG)"`

---

## Task 2: Wire fundamentals into the analyst skill

- [ ] **Step 1:** In `SKILL.md` data step, add: for any buy/valuation judgement run `./.venv/bin/python tools/fundamentals.py <TICKER>` and weigh valuation (P/E, PEG), growth, profitability and debt. For long-term core decisions, fundamentals are PRIMARY (vs technicals which are timing).
- [ ] **Step 2: Commit** `git add .claude/skills/traid-analyst/SKILL.md && git commit -m "feat: analyst uses deep fundamentals for value judgement"`

---

## Task 3: README + full suite

- [ ] **Step 1:** Add usage to `README.md`; mark Phase 5 done.
- [ ] **Step 2:** `./.venv/bin/pytest -q` → all pass.
- [ ] **Step 3: Commit** `git add README.md && git commit -m "docs: document fundamentals; mark Phase 5 done"`

---

## Self-Review
- Valuation (P/E, forward, PEG), growth, profitability, health all covered. ✓
- PEG computed when yfinance doesn't supply it. ✓
- Honest about heuristic thresholds + "no P/E" for unprofitable. ✓
- Pure classifiers unit-tested; live fetch smoke-tested. ✓
