#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# activate venv
if [ -f ".venv/bin/activate" ]; then
  # POSIX venv
  source .venv/bin/activate
elif [ -f ".venv/Scripts/activate" ]; then
  # Windows Git-Bash / WSL path
  source .venv/Scripts/activate
else
  echo ".venv not found. Create it first: python3 -m venv .venv && source .venv/bin/activate"
  exit 1
fi

# Ensure app package is importable (pi/app)
export PYTHONPATH="${PYTHONPATH:-}:$PWD/pi"

# Defaults (override via env before calling ./start.sh if needed)
export LT_DB_PATH="${LT_DB_PATH:-$PWD/pi/data/lighttracker.db}"
export MQTT_HOST="${MQTT_HOST:-localhost}"
export MQTT_PORT="${MQTT_PORT:-1883}"
export DMX_UART_DEVICE="${DMX_UART_DEVICE:-/dev/ttyUSB0}"

# Ensure DB directory exists
db_dir="$(dirname "$LT_DB_PATH")"
mkdir -p "$db_dir"

# Bind host/port (override with HOST / PORT envs)
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "Starting LightTracker API on $HOST:$PORT (DB=$LT_DB_PATH)..."
exec uvicorn app.main:app --host "$HOST" --port "$PORT"
