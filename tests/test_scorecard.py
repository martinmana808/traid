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
