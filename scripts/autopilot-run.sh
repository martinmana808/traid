#!/usr/bin/env bash
# Scheduled TRaid Autopilot run (launchd). The headless `claude` session's own
# --model IS the brain (Fable through Jul 7, then Opus). caffeinate keeps the Mac
# awake for the run. All paper — no real orders.
set -euo pipefail
cd "$(dirname "$0")/.."

# Ensure the runtime dir exists before any redirect (gitignored, so absent on fresh checkout).
mkdir -p data/autopilot

LOG="data/autopilot/run.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] $*" >> "$LOG"; }

log "run start"

# Token saver: only invoke the brain when the US market is actually open. On closed
# hours (nights/weekends/holidays) just refresh the status file with a cheap local
# Python call — no headless claude session, no tokens.
if ! ./.venv/bin/python -c "from datetime import datetime, timezone; from tools.autopilot_clock import is_market_open; import sys; sys.exit(0 if is_market_open(datetime.now(timezone.utc)) else 1)"; then
  if ./.venv/bin/python tools/autopilot.py execute '[]' > /dev/null 2>> "$LOG"; then
    log "market CLOSED — status refreshed, brain skipped (no tokens)"
  else
    log "market CLOSED — status refresh FAILED (see above)"
  fi
  exit 0
fi

MODEL="$(./.venv/bin/python tools/autopilot.py brain-model)"
if [ -z "$MODEL" ]; then
  log "ERROR: could not determine brain model; aborting"
  exit 1
fi
PROMPT="$(cat tools/autopilot_prompt.md)"

# launchd runs with a minimal PATH that won't find `claude`, so resolve to an absolute
# path: try PATH first, then known install locations.
CLAUDE_BIN="$(command -v claude || true)"
for _c in "$HOME/.local/bin/claude" "/opt/homebrew/bin/claude" "/usr/local/bin/claude" \
          "/Applications/cmux.app/Contents/Resources/bin/claude"; do
  [ -z "$CLAUDE_BIN" ] && [ -x "$_c" ] && CLAUDE_BIN="$_c"
done
if [ -z "$CLAUDE_BIN" ] || [ ! -x "$CLAUDE_BIN" ]; then
  log "ERROR: could not locate the 'claude' CLI; aborting"
  exit 1
fi

log "market OPEN — brain=$MODEL — invoking headless session"

# --print runs headless under the subscription; --allowedTools Bash lets the brain run
# the python autopilot CLI unattended (rails still enforced in Python regardless). The
# prompt goes via STDIN because --allowedTools is variadic and would otherwise swallow a
# positional prompt argument. The brain's own stderr is appended to the log.
if BRAIN_OUT="$(printf '%s' "$PROMPT" | caffeinate -i "$CLAUDE_BIN" -p --model "$MODEL" --allowedTools "Bash" 2>> "$LOG")"; then
  log "brain summary: $BRAIN_OUT"
else
  log "ERROR: brain session exited non-zero (see above)"
fi
log "run complete"
