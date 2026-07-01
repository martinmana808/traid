"""Deep fundamentals for TRaid (Phase 5).

Pulls valuation, growth, profitability, and financial-health metrics and turns
them into plain-English readings + an honest summary, so the analyst can judge
"good business at a fair price?" with data rather than guesswork.

Usage:
    python tools/fundamentals.py NVDA
    python tools/fundamentals.py AIR --market NZX

Honesty: uses latest available YoY figures from yfinance — not a hand-audited
multi-year model. Bucket thresholds are rough heuristics. Says "no P/E" for
unprofitable names rather than inventing one.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.market import normalize_ticker, error_response  # noqa: E402


# --- pure classifiers ------------------------------------------------------
def compute_peg(pe, earnings_growth_pct):
    """PEG = P/E divided by earnings growth %. None if either is missing or
    growth is non-positive (PEG is meaningless then)."""
    if pe is None or not earnings_growth_pct or earnings_growth_pct <= 0:
        return None
    return round(pe / earnings_growth_pct, 2)


def classify_pe(pe):
    if pe is None:
        return ("n/a", "no P/E (unprofitable or no data)")
    if pe < 15:
        return ("low", f"P/E {pe} — low (cheap, or low growth expectations)")
    if pe < 25:
        return ("moderate", f"P/E {pe} — moderate")
    if pe < 40:
        return ("elevated", f"P/E {pe} — elevated (priced for growth)")
    return ("high", f"P/E {pe} — high (priced for strong growth; needs to deliver)")


def classify_growth(g):
    if g is None:
        return ("n/a", "growth data unavailable")
    if g < 0:
        return ("shrinking", f"{g}% — shrinking")
    if g < 5:
        return ("slow", f"{g}% — slow")
    if g < 20:
        return ("solid", f"{g}% — solid")
    return ("strong", f"{g}% — strong")


def classify_margin(m):
    if m is None:
        return ("n/a", "margin data unavailable")
    if m < 0:
        return ("unprofitable", f"{m}% — unprofitable (losing money)")
    if m < 5:
        return ("thin", f"{m}% — thin")
    if m < 20:
        return ("healthy", f"{m}% — healthy")
    return ("high", f"{m}% — high (strong pricing power)")


def classify_health(debt_to_equity):
    if debt_to_equity is None:
        return ("n/a", "debt data unavailable")
    if debt_to_equity < 0.5:
        return ("low debt", f"debt/equity {debt_to_equity} — low (sturdy balance sheet)")
    if debt_to_equity < 1.5:
        return ("moderate debt", f"debt/equity {debt_to_equity} — moderate")
    return ("high debt", f"debt/equity {debt_to_equity} — high (more fragile)")


# --- helpers ---------------------------------------------------------------
def _pct(x):
    return None if x is None else round(x * 100, 1)


def _round(x, n=2):
    return None if x is None else round(x, n)


# --- live assembly ---------------------------------------------------------
def analyze(ticker, market=None):
    sym = normalize_ticker(ticker, market)
    try:
        import yfinance as yf
        info = yf.Ticker(sym).info
    except Exception as e:  # noqa: BLE001
        return error_response(f"fundamentals: fetch failed for {sym}: {e}")
    if not info or not info.get("shortName"):
        return error_response(f"fundamentals: no data for {sym}")

    trailing_pe = _round(info.get("trailingPE"))
    forward_pe = _round(info.get("forwardPE"))
    rev_growth = _pct(info.get("revenueGrowth"))
    earn_growth = _pct(info.get("earningsGrowth"))
    profit_margin = _pct(info.get("profitMargins"))
    roe = _pct(info.get("returnOnEquity"))
    d_e_raw = info.get("debtToEquity")  # yfinance reports this as a percent (e.g. 44.5 == 0.445)
    debt_to_equity = _round(d_e_raw / 100) if d_e_raw is not None else None

    peg = _round(info.get("trailingPegRatio")) or compute_peg(trailing_pe, earn_growth)

    pe_tag, pe_read = classify_pe(trailing_pe)
    g_tag, g_read = classify_growth(rev_growth)
    m_tag, m_read = classify_margin(profit_margin)
    h_tag, h_read = classify_health(debt_to_equity)

    summary = (
        f"{m_tag} margins, {g_tag} revenue growth, {pe_tag} valuation"
        + (f" (PEG {peg})" if peg is not None else "")
        + f", {h_tag}."
    )

    snapshot = {
        "market_cap": info.get("marketCap"),
        "avg_volume": info.get("averageVolume") or info.get("averageVolume10days"),
        "dividend_yield": _pct(info.get("dividendYield")),
        "next_earnings": info.get("earningsTimestamp"),
        "week52_high": _round(info.get("fiftyTwoWeekHigh")),
        "week52_low": _round(info.get("fiftyTwoWeekLow")),
        "analyst_rating": info.get("recommendationKey"),
        "analyst_target": _round(info.get("targetMeanPrice")),
        "analyst_count": info.get("numberOfAnalystOpinions"),
    }

    return {
        "ticker": sym,
        "name": info.get("shortName"),
        "sector": info.get("sector"),
        "valuation": {
            "trailing_pe": trailing_pe, "forward_pe": forward_pe, "peg": peg,
            "price_to_book": _round(info.get("priceToBook")),
            "tag": pe_tag, "reading": pe_read,
        },
        "growth": {
            "revenue_growth_pct": rev_growth, "earnings_growth_pct": earn_growth,
            "tag": g_tag, "reading": g_read,
        },
        "profitability": {
            "profit_margin_pct": profit_margin, "roe_pct": roe,
            "tag": m_tag, "reading": m_read,
        },
        "health": {
            "debt_to_equity": debt_to_equity,
            "free_cash_flow": info.get("freeCashflow"),
            "total_cash": info.get("totalCash"), "total_debt": info.get("totalDebt"),
            "tag": h_tag, "reading": h_read,
        },
        "snapshot": snapshot,
        "summary": summary,
        "note": (
            "Latest YoY figures from public data — not a hand-audited multi-year model. "
            "Bucket labels are rough heuristics; judge against the sector and the story."
        ),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="TRaid deep fundamentals")
    p.add_argument("ticker")
    p.add_argument("--market", default=None)
    args = p.parse_args(argv)
    print(json.dumps(analyze(args.ticker, args.market), indent=2))


if __name__ == "__main__":
    main()
