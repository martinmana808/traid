"""Free market data CLI for TRaid (US + NZX via yfinance).

Usage (CLI):
    python tools/market.py quote AAPL
    python tools/market.py quote AIR --market NZX
    python tools/market.py history VOO 6mo
    python tools/market.py fundamentals MSFT
    python tools/market.py fx NZDUSD

Every command prints JSON. On any failure it prints {"error": "..."} and
exits 0 so the caller always gets parseable output.
"""
import argparse
import json


def normalize_ticker(ticker, market=None):
    t = ticker.strip().upper()
    m = market.upper() if market else None
    if m in ("NZX", "NZ") and not t.endswith(".NZ"):
        t = f"{t}.NZ"
    elif m in ("ASX", "AU") and not t.endswith(".AX"):
        t = f"{t}.AX"
    return t


def normalize_fx_pair(pair):
    p = pair.strip().upper().replace("/", "")
    return p if p.endswith("=X") else f"{p}=X"


def error_response(message):
    return {"error": message}


def _yf():
    import yfinance as yf  # imported lazily so pure-function tests need no network/dep
    return yf


def quote(ticker, market=None):
    sym = normalize_ticker(ticker, market)
    try:
        info = _yf().Ticker(sym).fast_info
        last = float(info["last_price"])
        prev = float(info["previous_close"])
        return {
            "ticker": sym,
            "price": last,
            "previous_close": prev,
            "change_pct": round((last / prev - 1) * 100, 2),
            "currency": info["currency"],
        }
    except Exception as e:  # noqa: BLE001 — surface any failure as structured JSON
        return error_response(f"quote failed for {sym}: {e}")


def history(ticker, period, market=None, interval="1d"):
    sym = normalize_ticker(ticker, market)
    try:
        df = _yf().Ticker(sym).history(period=period, interval=interval)
        if df.empty:
            return error_response(f"no history for {sym} ({period}/{interval})")
        # Intraday bars (e.g. 1h) share a calendar day, so a date-only stamp would
        # collide — use a per-bar UNIX timestamp. Daily+ intervals keep the date.
        intraday = interval.endswith(("h", "m"))
        rows = [
            {
                "date": (int(idx.timestamp()) if intraday else idx.date().isoformat()),
                "open": round(float(r["Open"]), 4),
                "high": round(float(r["High"]), 4),
                "low": round(float(r["Low"]), 4),
                "close": round(float(r["Close"]), 4),
                "volume": int(r["Volume"]),
            }
            for idx, r in df.iterrows()
        ]
        return {"ticker": sym, "period": period, "bars": rows}
    except Exception as e:  # noqa: BLE001
        return error_response(f"history failed for {sym}: {e}")


def fundamentals(ticker, market=None):
    sym = normalize_ticker(ticker, market)
    try:
        info = _yf().Ticker(sym).info
        keys = {
            "name": "shortName", "sector": "sector", "industry": "industry",
            "market_cap": "marketCap", "pe_ratio": "trailingPE",
            "dividend_yield": "dividendYield", "currency": "currency",
        }
        return {"ticker": sym, **{out: info.get(src) for out, src in keys.items()}}
    except Exception as e:  # noqa: BLE001
        return error_response(f"fundamentals failed for {sym}: {e}")


def fx(pair):
    sym = normalize_fx_pair(pair)
    try:
        rate = float(_yf().Ticker(sym).fast_info["last_price"])
        return {"pair": sym, "rate": rate}
    except Exception as e:  # noqa: BLE001
        return error_response(f"fx failed for {sym}: {e}")


def _build_parser():
    p = argparse.ArgumentParser(description="TRaid free market data")
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("quote"); q.add_argument("ticker"); q.add_argument("--market", default=None)
    h = sub.add_parser("history"); h.add_argument("ticker"); h.add_argument("period"); h.add_argument("--market", default=None)
    f = sub.add_parser("fundamentals"); f.add_argument("ticker"); f.add_argument("--market", default=None)
    x = sub.add_parser("fx"); x.add_argument("pair")
    return p


def main(argv=None):
    args = _build_parser().parse_args(argv)
    if args.cmd == "quote":
        out = quote(args.ticker, args.market)
    elif args.cmd == "history":
        out = history(args.ticker, args.period, args.market)
    elif args.cmd == "fundamentals":
        out = fundamentals(args.ticker, args.market)
    elif args.cmd == "fx":
        out = fx(args.pair)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
