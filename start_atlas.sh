#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 was not found inside Ubuntu/WSL."
  echo "Install it with: sudo apt update && sudo apt install python3 python3-venv"
  exit 1
fi

if [ ! -d .venv ]; then
  echo "Creating Sentinel environment..."
  python3 -m venv .venv
fi

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
if command -v powershell.exe >/dev/null 2>&1; then
  powershell.exe -NoProfile -Command "Start-Process 'http://127.0.0.1:5010/'" >/dev/null 2>&1 || true
else
  xdg-open http://127.0.0.1:5010/ >/dev/null 2>&1 || true
fi

echo "Sentinel Atlas: http://127.0.0.1:5010/"
echo "Ghost Hub:      http://127.0.0.1:5011/"
echo "Press Ctrl+C to stop both."
wait "$atlas_pid" "$ghost_pid"
