"""Free per-ticker headlines for TRaid Autopilot via yfinance.

Headlines only — no deep analysis. News-sentiment is noisy; the brain treats
these as a hint, like the momentum indicators. Never raises: returns [] on any
failure so one bad ticker can't sink a run.
"""


def _yf_fetch(ticker):
    import yfinance as yf
    return yf.Ticker(ticker).news or []


def _url(content):
    for key in ("canonicalUrl", "clickThroughUrl"):
        node = content.get(key) or {}
        if node.get("url"):
            return node["url"]
    return ""


def headlines(ticker, limit=3, _fetch=None):
    fetch = _fetch or _yf_fetch
    try:
        raw = fetch(ticker) or []
    except Exception:  # noqa: BLE001 — a bad news feed must not sink the run
        return []
    out = []
    for item in raw[:limit]:
        c = item.get("content", {}) if isinstance(item, dict) else {}
        out.append({
            "title": c.get("title", ""),
            "source": (c.get("provider") or {}).get("displayName", ""),
            "published": c.get("pubDate", ""),
            "url": _url(c),
        })
    return out
