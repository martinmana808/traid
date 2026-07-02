import json
from tools.autopilot_cache import get_fundamentals


def test_first_call_fetches_and_writes(tmp_path):
    calls = []
    def fake(t):
        calls.append(t)
        return {"ticker": t, "summary": "ok"}
    p = tmp_path / "fund.json"
    out = get_fundamentals("NVDA", "2026-07-06", str(p), _analyze=fake)
    assert out["summary"] == "ok"
    assert calls == ["NVDA"]
    saved = json.loads(p.read_text())
    assert saved["date"] == "2026-07-06"
    assert saved["tickers"]["NVDA"]["summary"] == "ok"


def test_same_day_uses_cache(tmp_path):
    calls = []
    def fake(t):
        calls.append(t)
        return {"ticker": t}
    p = tmp_path / "fund.json"
    get_fundamentals("NVDA", "2026-07-06", str(p), _analyze=fake)
    get_fundamentals("NVDA", "2026-07-06", str(p), _analyze=fake)
    assert calls == ["NVDA"]   # second call served from cache


def test_new_day_resets_cache(tmp_path):
    calls = []
    def fake(t):
        calls.append(t)
        return {"ticker": t}
    p = tmp_path / "fund.json"
    get_fundamentals("NVDA", "2026-07-06", str(p), _analyze=fake)
    get_fundamentals("NVDA", "2026-07-07", str(p), _analyze=fake)
    assert calls == ["NVDA", "NVDA"]
    saved = json.loads(p.read_text())
    assert saved["date"] == "2026-07-07"
