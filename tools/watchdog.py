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
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification {json.dumps(text)} with title {json.dumps(title)}'],
            check=False, timeout=10,
        )
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
    config = {"move_pct": float(os.environ.get("WATCHDOG_MOVE_PCT", 7)), "fif_warn": 45000}
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
    elif args.check:
        run_check(dry_run=args.dry_run)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
