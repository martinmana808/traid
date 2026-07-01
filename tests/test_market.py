from tools.market import normalize_ticker, normalize_fx_pair, error_response


def test_normalize_ticker_us_unchanged():
    assert normalize_ticker("aapl") == "AAPL"
    assert normalize_ticker("VOO", market="US") == "VOO"


def test_normalize_ticker_nzx_gets_suffix():
    assert normalize_ticker("AIR", market="NZX") == "AIR.NZ"
    assert normalize_ticker("air", market="NZ") == "AIR.NZ"


def test_normalize_ticker_nzx_idempotent():
    assert normalize_ticker("AIR.NZ", market="NZX") == "AIR.NZ"


def test_normalize_ticker_asx_gets_suffix():
    assert normalize_ticker("AZY", market="ASX") == "AZY.AX"
    assert normalize_ticker("del", market="AU") == "DEL.AX"
    assert normalize_ticker("DEL.AX", market="ASX") == "DEL.AX"


def test_normalize_fx_pair():
    assert normalize_fx_pair("NZDUSD") == "NZDUSD=X"
    assert normalize_fx_pair("nzd/usd") == "NZDUSD=X"
    assert normalize_fx_pair("NZDUSD=X") == "NZDUSD=X"


def test_error_response_shape():
    assert error_response("boom") == {"error": "boom"}


import tools.market as market


def test_history_passes_interval(monkeypatch):
    captured = {}

    class FakeHist:
        def __init__(self): self.empty = False
        def iterrows(self):
            import datetime
            idx = datetime.date(2026, 1, 2)
            row = {"Open": 1.0, "High": 2.0, "Low": 0.5, "close": 1.5}
            # use a tiny stand-in row object
            class R(dict):
                pass
            r = R({"Open": 1.0, "High": 2.0, "Low": 0.5, "Close": 1.5, "Volume": 10})
            class TS:
                def date(self_): return idx
            yield TS(), r

    class FakeTicker:
        def __init__(self, sym): pass
        def history(self, period, interval="1d"):
            captured["period"] = period
            captured["interval"] = interval
            return FakeHist()

    monkeypatch.setattr(market, "_yf", lambda: type("Y", (), {"Ticker": FakeTicker}))
    out = market.history("NVDA", "1y", interval="1wk")
    assert captured["interval"] == "1wk"
    assert out["bars"][0]["close"] == 1.5


def test_history_intraday_uses_unique_timestamps(monkeypatch):
    """1h bars share a calendar day, so they must get per-bar UNIX timestamps
    (unique + ascending) — a date-only stamp would collide and break the chart."""
    import datetime

    class TS:
        def __init__(self, dt):
            self._dt = dt
        def timestamp(self):
            return self._dt.timestamp()
        def date(self):
            return self._dt.date()

    src = [
        (TS(datetime.datetime(2026, 6, 30, 9, 30)),
         {"Open": 1.0, "High": 2.0, "Low": 0.5, "Close": 1.5, "Volume": 10}),
        (TS(datetime.datetime(2026, 6, 30, 10, 30)),
         {"Open": 1.5, "High": 2.5, "Low": 1.0, "Close": 2.0, "Volume": 20}),
    ]

    class FakeDF:
        empty = False
        def iterrows(self):
            return iter(src)

    class FakeTicker:
        def __init__(self, sym): pass
        def history(self, period, interval="1d"):
            return FakeDF()

    monkeypatch.setattr(market, "_yf", lambda: type("Y", (), {"Ticker": FakeTicker}))
    out = market.history("NVDA", "3mo", interval="1h")
    times = [b["date"] for b in out["bars"]]
    assert all(isinstance(t, int) for t in times)     # intraday → int timestamps
    assert len(set(times)) == 2                        # unique per bar, not collapsed to one date
    assert times == sorted(times)                      # ascending
