# TRaid two-way Telegram bot

Reply to your daily digests — or just message the bot any time — and TRaid
answers. Free: the **Groq** brain (same one the digest uses) on a **Vercel**
serverless webhook. Heavy/deep analysis still happens at home in Claude Code.

- **Inbound (new):** `api/telegram.mjs` — a Vercel webhook. Stateless: context is
  your portfolio (a Vercel secret) + the digest you replied to (Telegram sends the
  quoted text). Only your chat id is answered; a webhook secret blocks forgeries.
- **Outbound (unchanged):** `tools/watchdog.py --tech-digest` on GitHub Actions.
  Setting a webhook does **not** affect it — the digest only *sends*, never polls.

## One-time setup

### 1. Deploy to Vercel
From the repo root (first run links the project):
```bash
vercel          # preview deploy — gives a URL to test
vercel --prod   # production deploy — use this URL for the webhook
```

### 2. Set environment variables (Vercel dashboard → Settings → Environment Variables)
**Never put these in the repo** — `data/portfolio.json` is gitignored for a reason.

| Var | Value |
|-----|-------|
| `TELEGRAM_BOT_TOKEN` | same token as the digest bot (@BotFather) |
| `TELEGRAM_CHAT_ID` | your numeric chat id (`python tools/watchdog.py --get-chat-id`) |
| `TELEGRAM_WEBHOOK_SECRET` | any random string you invent (e.g. `openssl rand -hex 16`) |
| `GROQ_API_KEY` | free key from console.groq.com (your existing `GROK_API_KEY` value works too) |
| `GROQ_MODEL` | *(optional)* default `llama-3.3-70b-versatile` |
| `PORTFOLIO_JSON` | *(optional)* compact holdings snapshot so it can answer portfolio questions |

> Tip for `PORTFOLIO_JSON`: paste a trimmed version of `data/portfolio.json`
> (tickers + shares + avg_cost is plenty). It lives only in Vercel's encrypted
> env, never the public repo. Update it when your holdings change.

Re-deploy (`vercel --prod`) after adding env vars so the function picks them up.

### 3. Register the webhook
```bash
TELEGRAM_BOT_TOKEN=... TELEGRAM_WEBHOOK_SECRET=... \
  scripts/telegram-set-webhook.sh https://<your-app>.vercel.app
```
(`TELEGRAM_WEBHOOK_SECRET` here must match the Vercel env var exactly.)

### 4. Test
- Message the bot in Telegram → it replies.
- Reply to a digest message → it answers *about that digest*.

## Maintenance / notes
- **Cost:** $0 — Groq free tier + Vercel Hobby + Telegram.
- **Smoke test the pure logic:** `node scripts/telegram-smoke-test.mjs`
- **Inspect the webhook:** `curl -s https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo | python3 -m json.tool`
- **Disable the bot:** delete the webhook → `curl https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/deleteWebhook` (digest keeps working).
- **Want it to remember earlier messages?** v1 is stateless by design (smallest
  blast radius). Rolling memory is a clean add-on later (small Upstash Redis).
