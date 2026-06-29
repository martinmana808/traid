"""Interactive chart CLI for TRaid (Phase 7 — the 'Screen').

Generates a self-contained, zoomable/pannable TradingView-style HTML chart for a
ticker. Two modes:
  - live (default): fresh data -> charts/live/<TICKER>-<date>.html
  - snapshot:       frozen per-call copy -> charts/sessions/<date>/<TICKER>-<callid>.html

Usage:
    python tools/chart.py NVDA
    python tools/chart.py AIR --market NZX --period 2y
    python tools/chart.py META --snapshot --call-id 2026-06-28-001

Charts are personal output and gitignored. Decision-support, not financial advice.
"""
import argparse
import json
import os
import sys
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.chart_data import build_chart_data  # noqa: E402
from tools.chart_render import render_chart_html, render_session_index  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def write_chart(chart_data, meta, out_dir, filename):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render_chart_html(chart_data, meta))
    return path


def _update_session_index(session_dir, date):
    """Rebuild index.html from the chart files present in a session dir."""
    entries = []
    for fn in sorted(os.listdir(session_dir)):
        if fn.endswith(".html") and fn != "index.html":
            ticker = fn.split("-", 1)[0]
            entries.append({"ticker": ticker, "call": None, "filename": fn})
    with open(os.path.join(session_dir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(render_session_index(date, entries))


def generate_chart(ticker, market=None, period="1y", snapshot=False,
                   call_id=None, call_meta=None, charts_root=None, open_browser=True):
    charts_root = charts_root or os.path.join(_ROOT, "charts")
    data = build_chart_data(ticker, market, period)
    if "error" in data:
        return data
    sym = data["ticker"]
    date = data["as_of"]
    meta = call_meta or {}

    if snapshot:
        session_dir = os.path.join(charts_root, "sessions", date)
        suffix = call_id or "snapshot"
        path = write_chart(data, meta, session_dir, f"{sym}-{suffix}.html")
        _update_session_index(session_dir, date)
    else:
        path = write_chart(data, meta, os.path.join(charts_root, "live"),
                           f"{sym}-{date}.html")

    if open_browser:
        webbrowser.open("file://" + os.path.abspath(path))
    return path


def main(argv=None):
    p = argparse.ArgumentParser(description="TRaid interactive chart")
    p.add_argument("ticker")
    p.add_argument("--market", default=None)
    p.add_argument("--period", default="1y")
    p.add_argument("--snapshot", action="store_true",
                   help="save a frozen per-call snapshot under charts/sessions/<date>/")
    p.add_argument("--call-id", default=None, help="ledger call id to tag a snapshot")
    p.add_argument("--call", default=None, help="TRaid call (buy/hold/trim/etc.) to show in the title")
    p.add_argument("--confidence", default=None, help="confidence (low/medium/high) to show in the title")
    p.add_argument("--call-date", default=None, help="date of the call to show in the title")
    args = p.parse_args(argv)
    call_meta = {}
    if args.call:
        call_meta["call"] = args.call
    if args.confidence:
        call_meta["confidence"] = args.confidence
    if args.call_date:
        call_meta["call_date"] = args.call_date
    result = generate_chart(args.ticker, args.market, args.period,
                            snapshot=args.snapshot, call_id=args.call_id,
                            call_meta=call_meta or None)
    if isinstance(result, dict) and "error" in result:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps({"chart": result}, indent=2))


if __name__ == "__main__":
    main()
