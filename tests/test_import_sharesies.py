from tools.import_sharesies import (
    map_columns, normalize_type, normalize_market, num, aggregate,
)


SAMPLE_HEADER = [
    "Transaction date", "Transaction type", "Instrument code", "Company name",
    "Market", "Currency", "Number of shares", "Share price", "Transaction value",
]


def test_map_columns_finds_all_fields():
    m = map_columns(SAMPLE_HEADER)
    assert m["date"] == 0
    assert m["type"] == 1
    assert m["symbol"] == 2
    assert m["name"] == 3
    assert m["market"] == 4
    assert m["currency"] == 5
    assert m["quantity"] == 6
    assert m["price"] == 7


def test_map_columns_reports_missing():
    m = map_columns(["Date", "Code", "Shares"])  # no type/price
    assert m["type"] is None
    assert m["price"] is None


def test_normalize_type():
    assert normalize_type("Buy") == "buy"
    assert normalize_type("BUY") == "buy"
    assert normalize_type("Sell") == "sell"
    assert normalize_type("dividend") is None


def test_normalize_market():
    assert normalize_market("US") == "US"
    assert normalize_market("NZX") == "NZX"
    assert normalize_market("nz") == "NZX"
    assert normalize_market("ASX") == "ASX"
    assert normalize_market("au") == "ASX"


def test_num_strips_symbols_and_commas():
    assert num("$1,100.50") == 1100.5
    assert num("5") == 5.0
    assert num("") is None


def test_aggregate_net_shares_and_avg_cost():
    txns = [
        {"type": "buy", "symbol": "NVDA", "name": "NVIDIA", "market": "US", "currency": "USD", "qty": 5, "price": 100.0},
        {"type": "buy", "symbol": "NVDA", "name": "NVIDIA", "market": "US", "currency": "USD", "qty": 5, "price": 120.0},
        {"type": "sell", "symbol": "NVDA", "name": "NVIDIA", "market": "US", "currency": "USD", "qty": 2, "price": 150.0},
        {"type": "buy", "symbol": "AIR", "name": "Air NZ", "market": "NZX", "currency": "NZD", "qty": 100, "price": 1.50},
    ]
    holdings = {h["ticker"]: h for h in aggregate(txns)}
    assert holdings["NVDA"]["shares"] == 8          # 10 bought - 2 sold
    assert holdings["NVDA"]["avg_cost"] == 110.0     # 1100 cost / 10 bought
    assert holdings["NVDA"]["market"] == "US"
    assert holdings["AIR"]["shares"] == 100
    assert holdings["AIR"]["avg_cost"] == 1.5


def test_aggregate_drops_fully_sold_positions():
    txns = [
        {"type": "buy", "symbol": "X", "name": "X", "market": "US", "currency": "USD", "qty": 3, "price": 10.0},
        {"type": "sell", "symbol": "X", "name": "X", "market": "US", "currency": "USD", "qty": 3, "price": 12.0},
    ]
    assert aggregate(txns) == []
