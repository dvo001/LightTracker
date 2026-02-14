#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Resolve venv python directly to avoid stale absolute paths inside activate scripts.
if [ -x ".venv/bin/python" ]; then
  VENV_PY=".venv/bin/python"
elif [ -x ".venv/Scripts/python.exe" ]; then
  VENV_PY=".venv/Scripts/python.exe"
elif [ -x ".venv/Scripts/python" ]; then
  VENV_PY=".venv/Scripts/python"
else
  echo ".venv python not found. Create it first:"
  echo "  python3 -m venv .venv"
  echo "  .venv/bin/pip install -r pi/requirements.txt"
  exit 1
fi

# Ensure app package is importable (pi/app)
export PYTHONPATH="${PYTHONPATH:-}:$PWD/pi"

# Defaults (override via env before calling ./start.sh if needed)
export LT_DB_PATH="${LT_DB_PATH:-$PWD/pi/app/data/lighttracker.db}"
export MQTT_HOST="${MQTT_HOST:-localhost}"
export MQTT_PORT="${MQTT_PORT:-1883}"
export DMX_UART_DEVICE="${DMX_UART_DEVICE:-/dev/ttyUSB0}"

# Ensure DB directory exists
db_dir="$(dirname "$LT_DB_PATH")"
mkdir -p "$db_dir"

# Bind host/port (override with HOST / PORT envs)
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

# Check runtime dependency early for clearer errors.
if ! "$VENV_PY" -c "import uvicorn" >/dev/null 2>&1; then
  echo "uvicorn is missing in .venv. Install dependencies:"
  echo "  $VENV_PY -m pip install -r pi/requirements.txt"
  exit 1
fi

echo "Starting LightTracker API on $HOST:$PORT (DB=$LT_DB_PATH)..."
exec "$VENV_PY" -m uvicorn app.main:app --host "$HOST" --port "$PORT"
