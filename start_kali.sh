#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
. .venv/bin/activate
python -m pip install -r requirements.txt
export ATLAS_URL=http://127.0.0.1:5010
export GHOST_HUB_URL=http://127.0.0.1:5011
python app.py &
atlas_pid=$!
python ghost_hub/ghost_hub.py &
ghost_pid=$!
trap 'kill "$atlas_pid" "$ghost_pid" 2>/dev/null || true' EXIT INT TERM
sleep 2
xdg-open http://127.0.0.1:5010/ >/dev/null 2>&1 || true
wait "$atlas_pid" "$ghost_pid"
