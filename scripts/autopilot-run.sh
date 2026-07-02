#!/usr/bin/env bash
# Hourly TRaid Autopilot run. The headless `claude` session's own --model IS
# the brain (Fable through Jul 7, then Opus). caffeinate keeps the Mac awake
# for the run. All paper — no real orders.
set -euo pipefail
cd "$(dirname "$0")/.."

# Ensure the runtime dir exists before any redirect (it's gitignored, so absent on fresh checkout).
mkdir -p data/autopilot

MODEL="$(./.venv/bin/python tools/autopilot.py brain-model)"
if [ -z "$MODEL" ]; then
  echo "autopilot-run: could not determine brain model; aborting" >> data/autopilot/run.log
  exit 1
fi
PROMPT="$(cat tools/autopilot_prompt.md)"

# launchd runs with a minimal PATH that won't find `claude`, so resolve it to an
# absolute path (falls back to the known cmux-bundled location).
CLAUDE_BIN="$(command -v claude || true)"
[ -z "$CLAUDE_BIN" ] && CLAUDE_BIN="/Applications/cmux.app/Contents/Resources/bin/claude"

# -i prevents idle sleep during the run. --print runs headless under the subscription;
# --allowedTools Bash lets the brain run the python autopilot CLI unattended (no other
# tools are permitted — and the money rails are enforced in Python regardless).
caffeinate -i "$CLAUDE_BIN" -p --model "$MODEL" --allowedTools "Bash" "$PROMPT" \
  >> data/autopilot/run.log 2>&1
