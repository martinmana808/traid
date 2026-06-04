# TRaid Phase 3 — Self-Verifying Scorecard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use `- [ ]` checkboxes.

**Goal:** Close the feedback loop — automatically verify matured predictions against actual prices, score them, and produce an honest, calibrated track record the analyst feeds back into future advice.

**Architecture:** A new `tools/scorecard.py`. Pure functions (horizon parsing, call evaluation, summarisation with sample-size honesty) are unit-tested; `run()` fetches actual prices (reusing `tools.market`/yfinance + `tools.ledger`) and assembles the scorecard. Verdicts are derived on the fly from the immutable ledger — no separate results file. Open calls get an interim (unrealized) mark.

**Tech Stack:** Python 3, yfinance, pandas, pytest.

**Scoring model (honest, v1):**
- Direction from reference price with a 1% deadband. `buy` correct if it rose; `sell`/`trim`/`avoid` correct if it fell; within deadband = "push" (unscored); `hold` = tracked, not scored.
- Hit-rate counts only **matured + directional** calls. Below `MIN_SAMPLE` (5) matured calls, no hit-rate is claimed.
- Calibration = hit-rate bucketed by confidence (low/med/high) and by call type.
- Returns are vs reference price (benchmark-relative scoring is a future upgrade — stated openly).

---

## File Structure
- `tools/scorecard.py` — pure scoring functions + `run()` + CLI
- `tests/test_scorecard.py` — unit tests for pure functions
- `.claude/skills/traid-analyst/SKILL.md` — read scorecard each session; apply calibration
- `README.md` — document the tool; mark Phase 3 done

---

## Task 1: Pure scoring functions (TDD)

**Files:** Create `tools/scorecard.py`, `tests/test_scorecard.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_scorecard.py
from tools.scorecard import parse_horizon, maturity_date, evaluate_call, summarize


def test_parse_horizon_months():
    assert parse_horizon("12 months") == 360


def test_parse_horizon_range_takes_upper():
    assert parse_horizon("6-12 months") == 360


def test_parse_horizon_years_plus():
    assert parse_horizon("5+ years") == 1825


def test_parse_horizon_weeks():
    assert parse_horizon("3 weeks") == 21


def test_parse_horizon_unbounded_is_none():
    assert parse_horizon("ongoing") is None
    assert parse_horizon("") is None


def test_maturity_date():
    assert maturity_date("2026-01-01", 90).isoformat() == "2026-04-01"
    assert maturity_date("2026-01-01", None) is None


def test_evaluate_buy_correct_when_up():
    correct, ret = evaluate_call("buy", 100, 110)
    assert correct is True and ret == 10.0


def test_evaluate_buy_wrong_when_down():
    correct, _ = evaluate_call("buy", 100, 90)
    assert correct is False


def test_evaluate_trim_correct_when_down():
    correct, _ = evaluate_call("trim", 100, 90)
    assert correct is True


def test_evaluate_within_deadband_is_push():
    correct, _ = evaluate_call("buy", 100, 100.5)
    assert correct is None


def test_evaluate_hold_not_scored():
    correct, ret = evaluate_call("hold", 100, 130)
    assert correct is None and ret == 30.0


def test_summarize_insufficient_sample():
    results = [
        {"status": "matured", "correct": True, "confidence": "high", "call": "buy", "return_pct": 5},
        {"status": "matured", "correct": False, "confidence": "low", "call": "buy", "return_pct": -3},
    ]
    out = summarize(results)
    assert out["overall_hit_rate"] is None
    assert "need" in out["calibration_note"].lower()


def test_summarize_enough_sample_and_calibration():
    results = [
        {"status": "matured", "correct": True,  "confidence": "high", "call": "buy",  "return_pct": 5},
        {"status": "matured", "correct": True,  "confidence": "high", "call": "buy",  "return_pct": 8},
        {"status": "matured", "correct": True,  "confidence": "high", "call": "buy",  "return_pct": 3},
        {"status": "matured", "correct": False, "confidence": "low",  "call": "trim", "return_pct": 2},
        {"status": "matured", "correct": True,  "confidence": "low",  "call": "trim", "return_pct": -4},
        {"status": "open",    "correct": None,  "confidence": "high", "call": "buy",  "return_pct": 1},
    ]
    out = summarize(results)
    assert out["matured_scored"] == 5
    assert out["overall_hit_rate"] == 80.0
    assert out["by_confidence"]["high"]["hit_rate"] == 100.0
    assert out["by_confidence"]["low"]["hit_rate"] == 50.0
```

- [ ] **Step 2: Run — expect fail** `./.venv/bin/pytest tests/test_scorecard.py -v`

- [ ] **Step 3: Implement `tools/scorecard.py`** (see repository file — pure functions + run() + CLI).

- [ ] **Step 4: Run — expect pass** `./.venv/bin/pytest tests/test_scorecard.py -v`

- [ ] **Step 5: Live smoke test** `./.venv/bin/python tools/scorecard.py` → JSON with `calls` (interim) + `scorecard` honestly reporting insufficient matured calls.

- [ ] **Step 6: Commit** `git add tools/scorecard.py tests/test_scorecard.py && git commit -m "feat: self-verifying scorecard with confidence calibration"`

---

## Task 2: Wire scorecard into the analyst skill

- [ ] **Step 1:** In `SKILL.md` step 2 (track record), add: run `./.venv/bin/python tools/scorecard.py`, read the calibration, and **discount confidence where history shows overconfidence** (e.g. if high-confidence calls underperform their label). Be honest about small samples — don't over-read a thin record.
- [ ] **Step 2: Commit** `git add .claude/skills/traid-analyst/SKILL.md && git commit -m "feat: analyst reads scorecard and applies calibration"`

---

## Task 3: README + full suite

- [ ] **Step 1:** Add scorecard usage to `README.md`; mark Phase 3 done.
- [ ] **Step 2:** `./.venv/bin/pytest -q` → all pass.
- [ ] **Step 3: Commit** `git add README.md && git commit -m "docs: document scorecard; mark Phase 3 done"`

---

## Self-Review
- Verify → compare → calibrate loop covered (run + summarize). ✓
- Honest small-sample guard (MIN_SAMPLE). ✓
- Confidence calibration bucketed. ✓
- Pure functions unit-tested; live fetch smoke-tested. ✓
- Open calls handled (interim mark, not scored). ✓
