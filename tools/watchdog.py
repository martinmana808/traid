"""TRaid Proactive Watchdog (Phase 6).

Runs on a schedule (launchd), checks your portfolio + predictions for things
worth knowing, and pushes a concise alert to your iPhone (Telegram) and Mac
(native notification). Quiet when nothing matters; never re-nags (state dedupe).

Usage:
    python tools/watchdog.py --check               # run checks, send alerts
    python tools/watchdog.py --check --dry-run     # print what it WOULD send
    python tools/watchdog.py --test                # send a test notification
    python tools/watchdog.py --get-chat-id         # helper for Telegram setup

Secrets via env / .env (gitignored): TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import date
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLIO_PATH = os.path.join(ROOT, "data", "portfolio.json")
STATE_PATH = os.path.join(ROOT, "data", "watchdog_state.json")
ENV_PATH = os.path.join(ROOT, ".env")


# --- pure alert rules (the "signal vs noise" core) -------------------------
def evaluate_alerts(holdings, quotes, matured_predictions, fif_cost, state, config):
    """Return (alerts, new_state). Each alert: {level, title, message}.
    Dedupes matured-prediction alerts via state['alerted_ids']."""
    alerts = []
    new_state = {"alerted_ids": list(state.get("alerted_ids", []))}
    move = config.get("move_pct", 7)

    for h in holdings:
        q = quotes.get(h["ticker"])
        if q and q.get("change_pct") is not None and abs(q["change_pct"]) >= move:
            arrow = "📈" if q["change_pct"] > 0 else "📉"
            alerts.append({
                "level": "move",
                "title": f"{h['ticker']} big move",
                "message": f"{arrow} {h['ticker']} {q['change_pct']:+.1f}% today (now {q['price']}).",
            })

    for p in matured_predictions:
        if p["id"] not in new_state["alerted_ids"]:
            alerts.append({
                "level": "prediction",
                "title": "Prediction matured",
                "message": f"📒 Prediction {p['id']} ({p['call']} {p['ticker']}) has matured — time to review how it did.",
            })
            new_state["alerted_ids"].append(p["id"])

    if fif_cost is not None and fif_cost >= config.get("fif_warn", 45000):
        alerts.append({
            "level": "tax",
            "title": "FIF threshold nearing",
            "message": f"⚠️ Foreign-share cost ~${fif_cost:,.0f} NZD — approaching the $50k FIF tax threshold.",
        })

    return alerts, new_state


# --- env / state -----------------------------------------------------------
def load_env(path=ENV_PATH):
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# --- delivery --------------------------------------------------------------
def send_telegram(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False, "missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=15) as r:
            return r.status == 200, r.status
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def send_mac(title, text):
    # Pass text/title as argv so osascript needs no inline string escaping
    # (robust to em-dashes, emojis, quotes, etc.).
    script = "on run argv\ndisplay notification (item 1 of argv) with title (item 2 of argv)\nend run"
    try:
        subprocess.run(["osascript", "-e", script, text, title], check=False, timeout=10)
        return True
    except Exception:  # noqa: BLE001
        return False


# --- data gathering (network) ---------------------------------------------
def _gather():
    from tools.market import quote, fx
    from tools.scorecard import run as scorecard_run

    portfolio = load_json(PORTFOLIO_PATH, {"holdings": []})
    holdings = portfolio.get("holdings", [])

    quotes = {}
    for h in holdings:
        market = h.get("market")
        quotes[h["ticker"]] = quote(h["ticker"], market if market != "US" else None)

    report = scorecard_run()
    matured = [c for c in report.get("calls", []) if c.get("status") == "matured"]

    # foreign-share cost basis in NZD (FIF cost) = non-NZX holdings' cost
    nzdusd = fx("NZDUSD").get("rate")
    fif_cost = None
    if nzdusd:
        usd_to_nzd = 1 / nzdusd
        fif_cost = 0.0
        for h in holdings:
            if h.get("market") != "NZX":
                cost = h.get("shares", 0) * h.get("avg_cost", 0)
                fif_cost += cost * usd_to_nzd  # ASX in AUD is approximated via USD rate (tiny positions)
    return holdings, quotes, matured, fif_cost


def run_check(dry_run=False):
    config = {"move_pct": float(os.environ.get("WATCHDOG_MOVE_PCT", 5)), "fif_warn": 45000}
    holdings, quotes, matured, fif_cost = _gather()
    state = load_json(STATE_PATH, {"alerted_ids": []})
    alerts, new_state = evaluate_alerts(holdings, quotes, matured, fif_cost, state, config)

    if not alerts:
        print("Watchdog: nothing worth alerting. (quiet)")
        return
    body = "TRaid Watchdog:\n" + "\n".join(f"• {a['message']}" for a in alerts)
    print(body)
    if dry_run:
        print("\n(dry run — not sending)")
        return
    ok, info = send_telegram(body)
    send_mac("TRaid Watchdog", "; ".join(a["title"] for a in alerts))
    print(f"\nTelegram sent: {ok} ({info})")
    save_json(STATE_PATH, new_state)


def build_digest(holdings, quotes, fx_rate, date_str, notable=None):
    """Pure: build the daily portfolio digest message from holdings + quotes.
    fx_rate = NZDUSD (e.g. 0.588); USD/AUD valued in NZD via 1/fx_rate."""
    usd_nzd = (1.0 / fx_rate) if fx_rate else None
    rows, total, total_chg = [], 0.0, 0.0
    for h in holdings:
        q = quotes.get(h["ticker"])
        if not q or q.get("price") is None or q.get("change_pct") is None:
            continue
        val = h.get("shares", 0) * q["price"]
        val_nzd = val if h.get("currency") == "NZD" else (val * usd_nzd if usd_nzd else val)
        total += val_nzd
        total_chg += val_nzd * q["change_pct"] / 100.0
        rows.append((h["ticker"], q["change_pct"]))
    if not rows:
        return f"📊 TRaid Daily — {date_str}\nNo price data available right now."
    winner = max(rows, key=lambda r: r[1])
    loser = min(rows, key=lambda r: r[1])
    base = total - total_chg
    pct = (total_chg / base * 100) if base else 0.0
    lines = [
        f"📊 TRaid Daily — {date_str}",
        f"Portfolio: ${total:,.0f} NZD  (today {pct:+.1f}%, ${total_chg:+,.0f} NZD)",
        f"🟢 Winner: {winner[0]} {winner[1]:+.1f}%",
        f"🔴 Loser:  {loser[0]} {loser[1]:+.1f}%",
    ]
    if notable:
        lines.append(notable)
    return "\n".join(lines)


def run_digest(dry_run=False):
    from tools.market import quote, fx
    portfolio = load_json(PORTFOLIO_PATH, {"holdings": []})
    holdings = portfolio.get("holdings", [])
    quotes = {}
    for h in holdings:
        m = h.get("market")
        quotes[h["ticker"]] = quote(h["ticker"], m if m != "US" else None)
    fx_rate = fx("NZDUSD").get("rate")

    # heuristic "worth a look": is the day's biggest loser oversold?
    notable = None
    movers = [(t, q["change_pct"]) for t, q in quotes.items() if q.get("change_pct") is not None]
    if movers:
        loser_t = min(movers, key=lambda x: x[1])[0]
        try:
            from tools.indicators import analyze as ind
            h = next(x for x in holdings if x["ticker"] == loser_t)
            r = ind(loser_t, h.get("market") if h.get("market") != "US" else None)
            rsi = r.get("indicators", {}).get("rsi", {}).get("value")
            if rsi is not None and rsi < 35:
                notable = f"👀 {loser_t} oversold (RSI {rsi}) — ping TRaid for a buy read"
        except Exception:  # noqa: BLE001
            pass

    msg = build_digest(holdings, quotes, fx_rate, date.today().isoformat(), notable)
    print(msg)
    if dry_run:
        print("\n(dry run — not sending)")
        return
    ok, info = send_telegram(msg)
    send_mac("TRaid Daily", msg.split("\n", 2)[1] if "\n" in msg else "daily digest")
    print(f"\nTelegram sent: {ok} ({info})")


# --- AI tech-scene digest (Grok / xAI) ------------------------------------
# Broad tech/AI watchlist (NOT just holdings) — gives the "whole tech scene" view.
TECH_WATCHLIST = ["NVDA", "MSFT", "AAPL", "GOOGL", "AMZN", "META", "TSLA",
                  "AMD", "AVGO", "TSM", "ASML", "PLTR", "RKLB", "ARM", "MU", "QQQ"]


def gather_movers(tickers):
    from tools.market import quote
    out = []
    for t in tickers:
        q = quote(t)
        if q.get("change_pct") is not None:
            out.append({"ticker": t, "price": q.get("price"), "change_pct": q["change_pct"]})
    return out


def build_tech_prompt(movers, date_str):
    ranked = sorted(movers, key=lambda m: m["change_pct"], reverse=True)
    body = "\n".join(f"{m['ticker']}: {m['change_pct']:+.1f}% (${m['price']})" for m in ranked)
    return (
        f"Today is {date_str}. Daily % moves for major tech/AI stocks:\n{body}\n\n"
        "Write a SHORT (~110 words) daily tech digest for Martin (NZ investor; holds NVDA, TSLA, "
        "PLTR, RKLB, QQQ). Include: today's clear WINNER and LOSER of this group; the overall tech "
        "mood in one line; and 1-2 names 'worth a look' with a one-line HONEST reason (dip-buy? "
        "overheated? momentum?). No hype. Flag uncertainty. End with exactly: 'Ping TRaid to dig deeper.'"
    )


def groq_chat(prompt, api_key=None, model=None):
    # Groq (groq.com) — free, fast, OpenAI-compatible. Accepts GROQ_API_KEY or
    # the legacy GROK_API_KEY env name (so existing secrets keep working).
    api_key = api_key or os.environ.get("GROQ_API_KEY") or os.environ.get("GROK_API_KEY")
    model = model or os.environ.get("GROQ_MODEL") or os.environ.get("GROK_MODEL") or "llama-3.3-70b-versatile"
    if not api_key:
        return None, "missing GROQ_API_KEY"
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": "You are TRaid, a sharp, honest tech/AI market analyst. No hype; flag uncertainty; never give blind buy signals."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.6,
        "max_tokens": 400,
    }).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions", data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "TRaid/1.0 (+https://github.com/martinmana808/traid)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            d = json.load(r)
        return d["choices"][0]["message"]["content"].strip(), 200
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def run_tech_digest(dry_run=False):
    movers = gather_movers(TECH_WATCHLIST)
    if not movers:
        print("tech-digest: no market data")
        return
    today = date.today().isoformat()
    text, info = groq_chat(build_tech_prompt(movers, today))
    if text:
        msg = f"🤖 TRaid Tech Digest — {today}\n\n{text}"
    else:  # resilient fallback: plain winner/loser if Grok unavailable
        ranked = sorted(movers, key=lambda m: m["change_pct"], reverse=True)
        w, l = ranked[0], ranked[-1]
        msg = (f"📊 TRaid Tech — {today}\n"
               f"🟢 Winner: {w['ticker']} {w['change_pct']:+.1f}%\n"
               f"🔴 Loser:  {l['ticker']} {l['change_pct']:+.1f}%\n"
               f"(AI digest off: {info})")
    print(msg)
    if dry_run:
        print("\n(dry run — not sending)")
        return
    ok, sinfo = send_telegram(msg)
    send_mac("TRaid Tech Digest", "Daily tech-scene digest")
    print(f"\nTelegram sent: {ok} ({sinfo})")


def get_chat_id():
    load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Set TELEGRAM_BOT_TOKEN in .env first (from @BotFather).")
        return
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    with urllib.request.urlopen(url, timeout=15) as r:
        data = json.load(r)
    ids = {u["message"]["chat"]["id"] for u in data.get("result", []) if u.get("message")}
    if ids:
        print("Your chat id(s):", ", ".join(str(i) for i in ids))
        print("Put it in .env as TELEGRAM_CHAT_ID=<that number>")
    else:
        print("No messages yet. Send any message to your bot in Telegram, then re-run.")


def main(argv=None):
    load_env()
    p = argparse.ArgumentParser(description="TRaid proactive watchdog")
    p.add_argument("--check", action="store_true", help="run checks and send alerts")
    p.add_argument("--digest", action="store_true", help="send the daily portfolio digest")
    p.add_argument("--tech-digest", action="store_true", dest="tech_digest", help="send the AI tech-scene digest (Grok)")
    p.add_argument("--dry-run", action="store_true", help="print alerts without sending")
    p.add_argument("--test", action="store_true", help="send a test notification")
    p.add_argument("--get-chat-id", action="store_true", help="Telegram setup helper")
    args = p.parse_args(argv)

    if args.get_chat_id:
        get_chat_id()
    elif args.test:
        ok, info = send_telegram("✅ TRaid Watchdog test — notifications are working.")
        send_mac("TRaid Watchdog", "Test notification — it works!")
        print(f"Telegram: {ok} ({info}); Mac notification sent.")
    elif args.tech_digest:
        run_tech_digest(dry_run=args.dry_run)
    elif args.digest:
        run_digest(dry_run=args.dry_run)
    elif args.check:
        run_check(dry_run=args.dry_run)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
