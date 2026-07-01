# Phase 7.6 — Rich Info Panel (TradingView-style subset) Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Checkbox steps.

**Goal:** Enrich the chart's side panel with ticker-level context — key facts, multi-timeframe performance, analyst rating/target, and a derived technicals rating — using only data we can get (yfinance + our own series). Honest subset of TradingView's panel; not a full replica.

## Global Constraints
- No new Python deps (reuse yfinance via existing tools). Pure render for chart_render. `const DATA = __DATA__;\n` intact.
- All new fields degrade gracefully to "—" when unavailable (analyst/earnings often missing). Never fatal.
- Tests no-network (monkeypatch). Not-financial-advice framing; the technicals rating tooltip must say it's a simple mechanical tally, not advice.
- New panel sections are STATIC (ticker-level) — shown regardless of hover/selection, like the fundamentals block.

---

### Task 1: `snapshot` fields from yfinance in `fundamentals.analyze`

**Files:** Modify `tools/fundamentals.py`; Test `tests/test_fundamentals.py`.

**Interface:** `analyze()` return dict gains a `"snapshot"` key:
```
{"market_cap","avg_volume","dividend_yield","next_earnings",
 "week52_high","week52_low","analyst_rating","analyst_target","analyst_count"}
```
All from the same `info` dict already fetched (no extra network). Any missing field → `None`.

- [ ] **Step 1: Failing test** — add to `tests/test_fundamentals.py` a test that monkeypatches the yfinance `info` (mirror the existing fundamentals test's patching) to include `marketCap`, `averageVolume`, `dividendYield`, `fiftyTwoWeekHigh`, `fiftyTwoWeekLow`, `targetMeanPrice`, `recommendationKey`, `numberOfAnalystOpinions`, and asserts `analyze(...)["snapshot"]["market_cap"]` etc. are populated, and that a missing field → None. (Follow the existing test file's mocking style; if it patches `yfinance` import, do the same.)

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement.** In `tools/fundamentals.py` `analyze()`, after the existing `info` is fetched, build:
```python
    snapshot = {
        "market_cap": info.get("marketCap"),
        "avg_volume": info.get("averageVolume") or info.get("averageVolume10days"),
        "dividend_yield": _pct(info.get("dividendYield")),
        "next_earnings": info.get("earningsTimestamp"),   # epoch secs or None
        "week52_high": _round(info.get("fiftyTwoWeekHigh")),
        "week52_low": _round(info.get("fiftyTwoWeekLow")),
        "analyst_rating": info.get("recommendationKey"),  # e.g. 'buy','strong_buy'
        "analyst_target": _round(info.get("targetMeanPrice")),
        "analyst_count": info.get("numberOfAnalystOpinions"),
    }
```
and add `"snapshot": snapshot,` to the returned dict. (`_pct`/`_round` already exist in the file.)

- [ ] **Step 4: Run → pass** (full `tests/test_fundamentals.py`).
- [ ] **Step 5: Commit.** `git add tools/fundamentals.py tests/test_fundamentals.py && git commit -m "feat: fundamentals snapshot fields (mkt cap, avg vol, div yield, 52w, analyst, next earnings)"`

---

### Task 2: performance + technicals rating in `build_chart_payload`

**Files:** Modify `tools/chart_data.py`; Test `tests/test_chart_data.py`.

**Interface:** payload gains two top-level keys:
- `"performance"`: `{"w1","m1","m3","ytd","y1"}` — % change from the daily closes (None if not enough history).
- `"technicals"`: `{"score","label"}` — a mechanical tally from the latest daily bar; `label` ∈ {"Strong sell","Sell","Neutral","Buy","Strong buy"}.

- [ ] **Step 1: Failing tests** — add to `tests/test_chart_data.py`:
```python
def test_payload_has_performance_and_technicals(monkeypatch):
    def fake_history(t, p, m=None, interval="1d"):
        return {"ticker": "NVDA", "period": p, "bars": _bars(300)}
    monkeypatch.setattr(cd, "history", fake_history)
    monkeypatch.setattr(cd, "fundamentals_analyze", lambda t, m=None: None)
    pay = cd.build_chart_payload("nvda")
    assert set(pay["performance"]) == {"w1", "m1", "m3", "ytd", "y1"}
    assert pay["technicals"]["label"] in ("Strong sell","Sell","Neutral","Buy","Strong buy")
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement.** In `tools/chart_data.py`, add helpers and populate from the DAILY resolution's candles (the `default` resolution's series; use the raw daily `bars` closes you already build). Add:
```python
def _perf(closes):
    def pct(n):
        if len(closes) <= n:
            return None
        return round((closes[-1] / closes[-1 - n] - 1) * 100, 2)
    ytd = None
    # ytd: first close of the latest calendar year present in dates — computed by caller
    return {"w1": pct(5), "m1": pct(21), "m3": pct(63), "y1": pct(252), "ytd": ytd}


def _technicals(closes, highs, lows):
    """Simple mechanical tally of trend + momentum at the latest bar."""
    from tools.indicators import rsi, macd, stochastic, sma
    if len(closes) < 30:
        return {"score": 0, "label": "Neutral"}
    price = closes[-1]
    s50 = sma(closes, 50).iloc[-1] if len(closes) >= 50 else None
    s200 = sma(closes, 200).iloc[-1] if len(closes) >= 200 else None
    macd_line, sig, _ = macd(closes)
    r = rsi(closes).iloc[-1]
    k, d = stochastic(highs, lows, closes)
    signals = []
    if s50 is not None: signals.append(price > s50)
    if s200 is not None: signals.append(price > s200)
    if s50 is not None and s200 is not None: signals.append(s50 > s200)
    signals.append(macd_line.iloc[-1] > sig.iloc[-1])
    if r == r: signals.append(r > 50)            # NaN-safe
    kk, dd = k.iloc[-1], d.iloc[-1]
    if kk == kk and dd == dd: signals.append(kk > dd)
    net = sum(1 if s else -1 for s in signals)
    label = ("Strong buy" if net >= 4 else "Buy" if net >= 2
             else "Sell" if net <= -4 else "Sell" if net <= -2 else "Neutral")
    # tidy: symmetric mapping
    if net >= 4: label = "Strong buy"
    elif net >= 2: label = "Buy"
    elif net <= -4: label = "Strong sell"
    elif net <= -2: label = "Sell"
    else: label = "Neutral"
    return {"score": net, "label": label}
```
Then in `build_chart_payload`, using the DAILY bars (the ones already fetched for the `1d` resolution — capture their closes/highs/lows/dates before popping scratch keys, or recompute from `resolutions[default]`'s candles), compute:
```python
    dcandles = resolutions[default]["candles"]
    dcloses = [c["close"] for c in dcandles]
    dhighs = [c["high"] for c in dcandles]
    dlows = [c["low"] for c in dcandles]
    perf = _perf(dcloses)
    # ytd from the daily dates (date strings 'YYYY-MM-DD')
    dates = [c["time"] for c in dcandles if isinstance(c["time"], str)]
    if dates:
        yr = dates[-1][:4]
        first_of_year = next((i for i, dt in enumerate(dcandles) if isinstance(dcandles[i]["time"], str) and dcandles[i]["time"][:4] == yr), None)
        if first_of_year is not None and dcloses[first_of_year]:
            perf["ytd"] = round((dcloses[-1] / dcloses[first_of_year] - 1) * 100, 2)
    tech = _technicals(dcloses, dhighs, dlows)
```
and add `"performance": perf, "technicals": tech,` to the returned dict.

- [ ] **Step 4: Run → pass** (full `tests/test_chart_data.py`).
- [ ] **Step 5: Commit.** `git add tools/chart_data.py tests/test_chart_data.py && git commit -m "feat: payload performance (1W/1M/3M/YTD/1Y) + technicals rating"`

---

### Task 3: Render the rich panel sections

**Files:** Modify `tools/chart_render.py`; Test `tests/test_chart_render.py`.

**Requirements:** Add STATIC panel sections (shown in every panel render — like the fundamentals block) built in Python (a `_make_stats_block_html(payload)` mirroring `_make_fund_block_html`, injected via a `__STATS_BLOCK__` token, sanitized for backtick/`${` like the fund block). Sections:
- **Key facts:** Market cap (compact, e.g. 4.78T), Avg vol (30d, compact), 52w range (low–high), Next earnings (date from epoch, or "—"), Div yield (% or "—"). From `payload.fundamentals.snapshot` (may be null → omit section).
- **Performance:** rows 1W / 1M / 3M / YTD / 1Y with the % colored green (≥0) / red (<0) using `.bull`/`.bear`. From `payload.performance`.
- **Analyst:** rating (title-cased, e.g. "Strong Buy"), price target, "(n analysts)". From `payload.fundamentals.snapshot`; omit if no rating.
- **Technicals:** the `payload.technicals.label` shown prominently, colored (Strong buy/Buy → green, Sell/Strong sell → red, Neutral → gray). From `payload.technicals`.
- Each section header via `.sep` + `<h3>`. Add `data-tip` on the section labels; add TIPS entries `marketcap`, `avgvol`, `perf`, `analyst`, `technicals` (plain-English; technicals tip MUST say "a simple mechanical tally of trend + momentum — context, not advice").
- Place the stats block in the panel BELOW the existing dynamic rows and fundamentals (append `__STATS_BLOCK__` where the panel body template ends, so it appears in both summary and hover renders — same pattern as `__FUND_BLOCK__`).
- Update `_payload()` in tests to include `performance`, `technicals`, and `fundamentals.snapshot` so all render tests build a valid payload.

- [ ] **Step 1: Failing test** — add to `tests/test_chart_render.py`:
```python
def test_render_has_rich_panel_sections():
    pay = _payload()
    pay["performance"] = {"w1": -1.2, "m1": 3.4, "m3": 10.0, "ytd": 26.4, "y1": 14.7}
    pay["technicals"] = {"score": 3, "label": "Strong buy"}
    pay["fundamentals"] = {"name":"NVIDIA","sector":"Tech","valuation":{"peg":0.6,"reading":""},
        "snapshot":{"market_cap":4.78e12,"avg_volume":168e6,"dividend_yield":0.14,
                    "next_earnings":None,"week52_high":300,"week52_low":100,
                    "analyst_rating":"strong_buy","analyst_target":313.39,"analyst_count":42}}
    html = render_chart_html(pay)
    assert "Performance" in html and "Technicals" in html
    assert "Strong buy" in html or "Strong Buy" in html
    assert "Market cap" in html or "Mkt cap" in html
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `_make_stats_block_html` + `__STATS_BLOCK__` injection (sanitized) + TIPS entries + `_payload()` fixture update.
- [ ] **Step 4: Run → pass, then full suite** `./.venv/bin/python -m pytest -q`.
- [ ] **Step 5: Manual smoke (network):** `./.venv/bin/python tools/chart.py NVDA` — confirm the panel shows Key facts, Performance (colored), Analyst, and a Technicals rating; hover tooltips on the new labels; nothing crashes when a field is missing. (Headless: `grep -c "Technicals"`.)
- [ ] **Step 6: Commit.** `git add tools/chart_render.py tests/test_chart_render.py && git commit -m "feat: rich panel — key facts, performance, analyst, technicals rating"`

---

### Task 4: Docs

**Files:** `README.md`, `.claude/skills/traid-analyst/SKILL.md`.

- [ ] **Step 1:** Note the richer side panel (key facts, multi-timeframe performance, analyst rating/target, a derived technicals rating) in the chart docs.
- [ ] **Step 2:** SKILL.md chart bullet: same concise note.
- [ ] **Step 3: Commit.** `git add README.md .claude/skills/traid-analyst/SKILL.md && git commit -m "docs: note Phase 7.6 rich info panel"`

---

## Self-Review
Coverage: snapshot fields → Task 1; performance + technicals → Task 2; render sections + tooltips → Task 3; docs → Task 4. All new fields None-safe. Technicals rating honestly labeled a mechanical tally. Types: `payload.fundamentals.snapshot`, `payload.performance`, `payload.technicals` produced in Tasks 1-2, consumed by Task 3's render + `_payload()` fixture. `__STATS_BLOCK__` sanitized like `__FUND_BLOCK__`.
