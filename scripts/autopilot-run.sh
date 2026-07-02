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

# -i prevents idle sleep during the run; claude -p runs headless under the subscription.
caffeinate -i claude -p --model "$MODEL" "$PROMPT" >> data/autopilot/run.log 2>&1
