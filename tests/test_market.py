from tools.market import normalize_ticker, normalize_fx_pair, error_response


def test_normalize_ticker_us_unchanged():
    assert normalize_ticker("aapl") == "AAPL"
    assert normalize_ticker("VOO", market="US") == "VOO"


def test_normalize_ticker_nzx_gets_suffix():
    assert normalize_ticker("AIR", market="NZX") == "AIR.NZ"
    assert normalize_ticker("air", market="NZ") == "AIR.NZ"


def test_normalize_ticker_nzx_idempotent():
    assert normalize_ticker("AIR.NZ", market="NZX") == "AIR.NZ"


def test_normalize_fx_pair():
    assert normalize_fx_pair("NZDUSD") == "NZDUSD=X"
    assert normalize_fx_pair("nzd/usd") == "NZDUSD=X"
    assert normalize_fx_pair("NZDUSD=X") == "NZDUSD=X"


def test_error_response_shape():
    assert error_response("boom") == {"error": "boom"}
