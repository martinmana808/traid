#!/usr/bin/env bash
# Push the TRaid bot's env vars from your local .env up to the Vercel project
# (production). Idempotent — safe to re-run. Generates a webhook secret if you
# don't have one yet and appends it to .env so set-webhook.sh can reuse it.
#
# Usage:  scripts/vercel-push-env.sh
set -euo pipefail

SCOPE="${VERCEL_SCOPE:-martins-projects-c8742a0d}"

[[ -f .env ]] || { echo "No .env found in repo root."; exit 1; }
set -a; # shellcheck disable=SC1091
source .env; set +a

# Make a webhook secret once, and persist it to .env for set-webhook.sh.
if [[ -z "${TELEGRAM_WEBHOOK_SECRET:-}" ]]; then
  TELEGRAM_WEBHOOK_SECRET="$(openssl rand -hex 16)"
  echo "TELEGRAM_WEBHOOK_SECRET=${TELEGRAM_WEBHOOK_SECRET}" >> .env
  echo "Generated TELEGRAM_WEBHOOK_SECRET and saved it to .env"
fi

push() {
  local name="$1" val="${2:-}"
  if [[ -z "$val" ]]; then echo "skip  $name (empty)"; return; fi
  vercel env rm "$name" production --scope "$SCOPE" --yes >/dev/null 2>&1 || true
  printf '%s' "$val" | vercel env add "$name" production --scope "$SCOPE" >/dev/null
  echo "set   $name"
}

push TELEGRAM_BOT_TOKEN      "${TELEGRAM_BOT_TOKEN:-}"
push TELEGRAM_CHAT_ID        "${TELEGRAM_CHAT_ID:-}"
push TELEGRAM_WEBHOOK_SECRET "${TELEGRAM_WEBHOOK_SECRET:-}"
# function reads GROQ_API_KEY first, then GROK_API_KEY
push GROQ_API_KEY            "${GROQ_API_KEY:-${GROK_API_KEY:-}}"
push GROQ_MODEL              "${GROQ_MODEL:-}"
# optional: portfolio context (only if you've put PORTFOLIO_JSON in .env)
push PORTFOLIO_JSON          "${PORTFOLIO_JSON:-}"

echo
echo "Done. Now redeploy so the function picks up the vars, then register the webhook:"
echo "  vercel --prod --scope $SCOPE"
echo "  scripts/telegram-set-webhook.sh https://traid-zeta.vercel.app"
