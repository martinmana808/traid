"""Import a Sharesies transaction-report CSV into TRaid's portfolio.

SAFE read-only sync: Sharesies has no official API, so instead you export a CSV
(Sharesies -> Manage -> Download reports -> Transaction report CSV), drop it in,
and this builds your holdings (net shares + average cost) from your real trades.
No credentials, nothing leaves your machine.

The parser is FORMAT-TOLERANT: it fuzzy-matches column names, so it should cope
with header variations. If it can't find a needed column it tells you which.

Usage:
    python tools/import_sharesies.py path/to/transactions.csv            # dry run (prints)
    python tools/import_sharesies.py path/to/transactions.csv --write     # update data/portfolio.json
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PORTFOLIO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "portfolio.json")

# Field -> ordered list of lowercased substrings to look for in a header cell.
COLUMN_SYNONYMS = {
    "date": ["transaction date", "trade date", "date"],
    "type": ["transaction type", "order type", "buy/sell", "type"],
    "symbol": ["instrument code", "symbol", "ticker", "code"],
    "name": ["company name", "instrument name", "company", "fund", "name"],
    "market": ["market", "exchange"],
    "currency": ["currency", "ccy"],
    "quantity": ["number of shares", "shares", "quantity", "units", "qty"],
    "price": ["price per share", "share price", "unit price", "price"],
}
REQUIRED = ["type", "symbol", "quantity", "price"]


def map_columns(header):
    cells = [(i, str(c).strip().lower()) for i, c in enumerate(header)]
    mapping = {}
    for field, syns in COLUMN_SYNONYMS.items():
        found = None
        for syn in syns:  # try most-specific synonyms first
            for i, cell in cells:
                if syn in cell:
                    found = i
                    break
            if found is not None:
                break
        mapping[field] = found
    return mapping


def normalize_type(raw):
    s = str(raw).strip().lower()
    if "buy" in s:
        return "buy"
    if "sell" in s:
        return "sell"
    return None


def normalize_market(raw):
    s = str(raw).strip().lower()
    if s in ("us", "usd", "nasdaq", "nyse"):
        return "US"
    if s in ("nz", "nzx"):
        return "NZX"
    if s in ("au", "asx"):
        return "ASX"
    return raw.strip().upper() if raw else "US"


def num(raw):
    s = str(raw).strip().replace("$", "").replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        raise ValueError("CSV is empty")
    header, data = rows[0], rows[1:]
    mapping = map_columns(header)
    missing = [f for f in REQUIRED if mapping.get(f) is None]
    txns = []
    for r in data:
        def cell(field):
            idx = mapping.get(field)
            return r[idx] if idx is not None and idx < len(r) else ""
        ttype = normalize_type(cell("type"))
        if ttype is None:  # skip dividends, top-ups, FX, transfers
            continue
        qty, price = num(cell("quantity")), num(cell("price"))
        sym = cell("symbol").strip().upper()
        if not sym or qty is None or price is None:
            continue
        txns.append({
            "type": ttype, "symbol": sym, "name": cell("name").strip(),
            "market": normalize_market(cell("market")), "currency": (cell("currency").strip().upper() or "USD"),
            "qty": qty, "price": price,
        })
    return txns, header, mapping, missing


def aggregate(txns):
    acc = {}
    for t in txns:
        a = acc.setdefault(t["symbol"], {
            "ticker": t["symbol"], "name": t["name"], "market": t["market"],
            "currency": t["currency"], "bought_shares": 0.0, "bought_cost": 0.0, "sold_shares": 0.0,
        })
        if t["type"] == "buy":
            a["bought_shares"] += t["qty"]
            a["bought_cost"] += t["qty"] * t["price"]
        else:
            a["sold_shares"] += t["qty"]
    holdings = []
    for a in acc.values():
        net = round(a["bought_shares"] - a["sold_shares"], 6)
        if net <= 1e-9:
            continue
        avg_cost = round(a["bought_cost"] / a["bought_shares"], 4) if a["bought_shares"] else 0.0
        holdings.append({
            "ticker": a["ticker"], "market": a["market"], "shares": net,
            "avg_cost": avg_cost, "currency": a["currency"],
        })
    return sorted(holdings, key=lambda h: h["ticker"])


def main(argv=None):
    p = argparse.ArgumentParser(description="Import Sharesies transaction CSV into portfolio.json")
    p.add_argument("csv_path")
    p.add_argument("--write", action="store_true", help="update data/portfolio.json (default is dry-run)")
    args = p.parse_args(argv)

    txns, header, mapping, missing = parse_csv(args.csv_path)
    if missing:
        print(json.dumps({
            "error": f"Could not find these columns: {missing}",
            "detected_header": header,
            "column_mapping": mapping,
            "hint": "Tell me which header is which and I'll adjust COLUMN_SYNONYMS.",
        }, indent=2))
        return

    holdings = aggregate(txns)
    print(f"Parsed {len(txns)} buy/sell transactions -> {len(holdings)} current holdings:\n")
    for h in holdings:
        print(f"  {h['ticker']:6} {h['market']:4} {h['shares']:>12.4f} @ avg {h['avg_cost']} {h['currency']}")

    if args.write:
        existing = {}
        if os.path.exists(PORTFOLIO_PATH):
            with open(PORTFOLIO_PATH) as f:
                existing = json.load(f)
        existing["holdings"] = holdings
        existing.setdefault("base_currency", "NZD")
        existing.setdefault("cash_available", 0)
        existing.setdefault("risk_tolerance", "high")
        existing["_note"] = "Holdings imported from Sharesies transaction CSV (real cost basis)."
        with open(PORTFOLIO_PATH, "w") as f:
            json.dump(existing, f, indent=2)
        print(f"\n✅ Wrote {len(holdings)} holdings to {PORTFOLIO_PATH} (cash & risk preserved).")
    else:
        print("\n(dry run — re-run with --write to update data/portfolio.json)")


if __name__ == "__main__":
    main()
