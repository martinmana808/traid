"""Append-only prediction ledger for TRaid.

Usage (CLI):
    python tools/ledger.py log --ticker VOO --market US --type long-term \
        --call buy --confidence medium --horizon "12 months" \
        --reference-price 512.30 --reference-currency USD \
        --rationale "broad market DCA"
    python tools/ledger.py list [--limit N]
"""
import argparse
import json
from datetime import date
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "predictions.jsonl"

VALID_TYPES = {"long-term", "swing"}
VALID_CALLS = {"buy", "hold", "avoid", "trim", "sell"}
VALID_CONFIDENCE = {"low", "medium", "high"}


def list_entries(path=DEFAULT_PATH, limit=None):
    path = Path(path)
    if not path.exists():
        return []
    entries = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries[-limit:] if limit is not None else entries


def _next_id(existing, today):
    seq = sum(1 for e in existing if e.get("date") == today) + 1
    return f"{today}-{seq:03d}"


def log(entry, path=DEFAULT_PATH, today=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    today = today or date.today().isoformat()
    record = dict(entry)
    record.setdefault("date", today)
    record["id"] = _next_id(list_entries(path), record["date"])
    record.setdefault("target", None)
    record.setdefault("user_action", None)
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")
    return record


def _build_parser():
    p = argparse.ArgumentParser(description="TRaid prediction ledger")
    sub = p.add_subparsers(dest="cmd", required=True)

    lg = sub.add_parser("log", help="append a prediction")
    lg.add_argument("--ticker", required=True)
    lg.add_argument("--market", default="US")
    lg.add_argument("--type", dest="type_", choices=sorted(VALID_TYPES), default="long-term")
    lg.add_argument("--call", choices=sorted(VALID_CALLS), required=True)
    lg.add_argument("--rationale", default="")
    lg.add_argument("--confidence", choices=sorted(VALID_CONFIDENCE), default="medium")
    lg.add_argument("--horizon", default="")
    lg.add_argument("--reference-price", type=float, default=None)
    lg.add_argument("--reference-currency", default=None)
    lg.add_argument("--target", type=float, default=None)
    lg.add_argument("--path", default=str(DEFAULT_PATH))

    ls = sub.add_parser("list", help="list predictions")
    ls.add_argument("--limit", type=int, default=None)
    ls.add_argument("--path", default=str(DEFAULT_PATH))
    return p


def main(argv=None):
    args = _build_parser().parse_args(argv)
    if args.cmd == "log":
        entry = {
            "ticker": args.ticker, "market": args.market, "type": args.type_,
            "call": args.call, "rationale": args.rationale,
            "confidence": args.confidence, "horizon": args.horizon,
            "reference_price": args.reference_price,
            "reference_currency": args.reference_currency, "target": args.target,
        }
        print(json.dumps(log(entry, path=args.path), indent=2))
    elif args.cmd == "list":
        print(json.dumps(list_entries(args.path, limit=args.limit), indent=2))


if __name__ == "__main__":
    main()
