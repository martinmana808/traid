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
