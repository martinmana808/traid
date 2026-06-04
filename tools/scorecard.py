"""Self-verifying scorecard for TRaid (Phase 3 — the feedback loop).

Reads the prediction ledger, determines which calls have matured, fetches
actual prices, scores each call directionally, and produces an HONEST
scorecard with confidence calibration. Open calls get an interim mark.

Usage:
    python tools/scorecard.py                # scorecard from data/predictions.jsonl
    python tools/scorecard.py --path FILE    # custom ledger
    python tools/scorecard.py --summary      # add a human-readable summary

Honesty is the whole point: with too few matured calls it refuses to claim a
hit-rate. Returns are vs the reference price, not benchmark-adjusted (future
upgrade).
"""
import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.market import normalize_ticker  # noqa: E402
from tools.ledger import list_entries, DEFAULT_PATH  # noqa: E402

MIN_SAMPLE = 5
DEADBAND = 0.01
_UNIT_DAYS = {"year": 365, "yr": 365, "month": 30, "mo": 30, "week": 7, "wk": 7, "day": 1}
_BULLISH = {"buy"}
_BEARISH = {"sell", "trim", "avoid"}


# --- Pure functions --------------------------------------------------------
def parse_horizon(horizon):
    """Map a horizon string to a number of days. Ranges take the upper bound.
    Unbounded ('ongoing', no number, no unit) -> None (never matures)."""
    if not horizon:
        return None
    s = str(horizon).lower()
    nums = [int(n) for n in re.findall(r"\d+", s)]
    if not nums:
        return None
    for key, val in _UNIT_DAYS.items():
        if key in s:
            return max(nums) * val
    return None


def maturity_date(start, days):
    if days is None:
        return None
    if isinstance(start, str):
        start = datetime.strptime(start, "%Y-%m-%d").date()
    return start + timedelta(days=days)


def evaluate_call(call, ref, now_price, deadband=DEADBAND):
    """Return (correct: True|False|None, return_pct). None correctness = a
    'push' (within deadband) or an unscored call type like 'hold'."""
    if ref in (None, 0) or now_price is None:
        return None, None
    ret = (now_price - ref) / ref
    if call in _BULLISH:
        correct = True if ret > deadband else (False if ret < -deadband else None)
    elif call in _BEARISH:
        correct = True if ret < -deadband else (False if ret > deadband else None)
    else:  # 'hold' and anything else: tracked, not scored
        correct = None
    return correct, round(ret * 100, 2)


def _bucket(results, key):
    out = {}
    for r in results:
        out.setdefault(r.get(key), []).append(r)
    return out


def _rate(rs):
    scored = [r for r in rs if r.get("status") == "matured" and r.get("correct") is not None]
    if not scored:
        return {"n": 0, "hit_rate": None}
    hr = round(100 * sum(1 for r in scored if r["correct"]) / len(scored), 1)
    return {"n": len(scored), "hit_rate": hr}


def summarize(results):
    scored = [r for r in results if r.get("status") == "matured" and r.get("correct") is not None]
    n = len(scored)
    n_correct = sum(1 for r in scored if r["correct"])
    enough = n >= MIN_SAMPLE
    matured_returns = [
        r["return_pct"] for r in results
        if r.get("status") == "matured" and r.get("return_pct") is not None
    ]
    avg_ret = round(sum(matured_returns) / len(matured_returns), 2) if matured_returns else None
    return {
        "matured_scored": n,
        "correct": n_correct,
        "overall_hit_rate": round(100 * n_correct / n, 1) if (enough and n > 0) else None,
        "avg_return_pct_matured": avg_ret,
        "by_confidence": {c: _rate(rs) for c, rs in _bucket(results, "confidence").items()},
        "by_call": {t: _rate(rs) for t, rs in _bucket(results, "call").items()},
        "calibration_note": (
            f"{n} matured, scored calls — early but readable. Watch whether high-confidence "
            f"calls actually beat low-confidence ones."
            if enough else
            f"Only {n} matured, scored call(s) — need >= {MIN_SAMPLE} for a meaningful hit-rate. "
            f"Keep logging; the scorecard sharpens with time."
        ),
        "honesty": (
            "Hit-rate counts only matured, directional calls (buy vs sell/trim/avoid). "
            "'hold' is tracked, not scored. Returns are vs reference price, not benchmark-adjusted."
        ),
    }


# --- Live assembly (network) ----------------------------------------------
def run(path=DEFAULT_PATH, today=None):
    today = today or date.today()
    if isinstance(today, str):
        today = datetime.strptime(today, "%Y-%m-%d").date()
    entries = list_entries(path)

    import yfinance as yf
    hist_cache = {}
    results = []
    for e in entries:
        sym = normalize_ticker(e.get("ticker", ""), e.get("market"))
        ref = e.get("reference_price")
        start = e.get("date")
        horizon_days = parse_horizon(e.get("horizon"))
        mat = maturity_date(start, horizon_days)
        status = "matured" if (mat is not None and mat <= today) else "open"

        if sym not in hist_cache:
            try:
                hist_cache[sym] = yf.Ticker(sym).history(start=start)
            except Exception:  # noqa: BLE001
                hist_cache[sym] = None
        df = hist_cache[sym]

        price = None
        if df is not None and not df.empty:
            if status == "matured" and mat is not None:
                sub = df[df.index.date <= mat]
                price = float((sub if not sub.empty else df)["Close"].iloc[-1])
            else:
                price = float(df["Close"].iloc[-1])
        price = round(price, 4) if price is not None else None

        correct, ret = evaluate_call(e.get("call"), ref, price)
        if status != "matured":
            correct = None  # never show a verdict before a call matures; keep interim return
        results.append({
            "id": e.get("id"),
            "ticker": sym,
            "call": e.get("call"),
            "confidence": e.get("confidence"),
            "type": e.get("type"),
            "status": status,
            "maturity": mat.isoformat() if mat else None,
            "reference_price": ref,
            "latest_price": price,
            "return_pct": ret,
            "correct": correct,
        })

    return {"as_of": today.isoformat(), "calls": results, "scorecard": summarize(results)}


def _human_summary(report):
    sc = report["scorecard"]
    lines = [f"TRaid scorecard @ {report['as_of']}", ""]
    for c in report["calls"]:
        if c["status"] == "open":
            verdict = "— open (interim)"
        else:
            verdict = {True: "✓ right", False: "✗ wrong", None: "— push"}[c["correct"]]
        ret = f"{c['return_pct']:+.1f}%" if c["return_pct"] is not None else "n/a"
        lines.append(f"  {c['id']}  {c['call']:5} {c['ticker']:7} {c['status']:7} {ret:>8}  {verdict}")
    lines += ["", f"  Overall hit-rate: {sc['overall_hit_rate']}", f"  {sc['calibration_note']}"]
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description="TRaid self-verifying scorecard")
    p.add_argument("--path", default=str(DEFAULT_PATH))
    p.add_argument("--summary", action="store_true", help="print a human-readable summary too")
    args = p.parse_args(argv)
    report = run(path=args.path)
    print(json.dumps(report, indent=2))
    if args.summary:
        print("\n" + _human_summary(report))


if __name__ == "__main__":
    main()
