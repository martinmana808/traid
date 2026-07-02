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


def test_failed_quote_does_not_zero_out_holding():
    # Hold 4 NVDA at cost 100; quote fails (price None). Must mark at avg_cost, not $0.
    acct = apply_fill(new_account(5000.0), "buy", "NVDA", 4, 100.0)
    deps = _deps()
    deps["price"] = lambda t: None            # every quote fails
    snap = build_snapshot(OPEN_UTC, ["NVDA"], acct, deps)
    nvda = next(p for p in snap["account"]["positions"] if p["ticker"] == "NVDA")
    assert nvda["price"] == 100.0             # fell back to avg_cost, NOT 0.0
    assert nvda["pnl_pct"] == 0.0             # not -100%
    assert snap["tickers"]["NVDA"]["price"] is None   # raw field still reports the failure
