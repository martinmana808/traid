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
