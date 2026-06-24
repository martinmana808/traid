#!/usr/bin/env bash
# Point your Telegram bot at the deployed Vercel webhook (one-time, re-run if the
# URL or secret changes). Setting a webhook does NOT affect the daily digest —
# the digest only SENDS messages; it never polls.
#
# Usage:
#   TELEGRAM_BOT_TOKEN=... TELEGRAM_WEBHOOK_SECRET=... \
#     scripts/telegram-set-webhook.sh https://traid.vercel.app
#
# (It also reads TELEGRAM_BOT_TOKEN / TELEGRAM_WEBHOOK_SECRET from .env if present.)
set -euo pipefail

# Load .env if the vars aren't already exported.
if [[ -f .env ]]; then
  set -a; # shellcheck disable=SC1091
  source .env; set +a
fi

BASE_URL="${1:-}"
TOKEN="${TELEGRAM_BOT_TOKEN:-}"
SECRET="${TELEGRAM_WEBHOOK_SECRET:-}"

[[ -z "$BASE_URL" ]] && { echo "Usage: $0 https://<your-vercel-app>.vercel.app"; exit 1; }
[[ -z "$TOKEN" ]] && { echo "Missing TELEGRAM_BOT_TOKEN (export it or put it in .env)"; exit 1; }
[[ -z "$SECRET" ]] && { echo "Missing TELEGRAM_WEBHOOK_SECRET (make one up; must match the Vercel env var)"; exit 1; }

WEBHOOK_URL="${BASE_URL%/}/api/telegram"
echo "Registering webhook: $WEBHOOK_URL"

curl -fsS "https://api.telegram.org/bot${TOKEN}/setWebhook" \
  --data-urlencode "url=${WEBHOOK_URL}" \
  --data-urlencode "secret_token=${SECRET}" \
  --data-urlencode 'allowed_updates=["message"]'
echo
echo "Done. Verify with (reads the token from .env, doesn't print it):"
echo '  curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool'
