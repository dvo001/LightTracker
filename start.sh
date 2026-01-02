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

# Defaults (override before calling ./start.sh if needed)
# Align with app.db:get_db_path, but allow override for deployments
export LT_DB_PATH="${LT_DB_PATH:-$PWD/pi/data/lighttracker.db}"
export MQTT_HOST="${MQTT_HOST:-localhost}"
export MQTT_PORT="${MQTT_PORT:-1883}"
export DMX_UART_DEVICE="${DMX_UART_DEVICE:-/dev/ttyUSB0}"

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
