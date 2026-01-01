#!/usr/bin/env bash
set -euo pipefail

BASE="http://127.0.0.1:8000"

echo "Check state..."
curl -sS "$BASE/api/v1/state" | jq '.'

echo "Check anchors..."
curl -sS "$BASE/api/v1/anchors" | jq '.'

echo "Insert anchor position..."
curl -sS -X POST "$BASE/api/v1/anchors/position" -H 'Content-Type: application/json' -d '{"mac":"AA:BB:CC:11:22:33","x_cm":100,"y_cm":200,"z_cm":300}' | jq '.'

echo "Check fixtures..."
curl -sS "$BASE/api/v1/fixtures" | jq '.'

echo "Health..."
curl -sS "$BASE/api/v1/health" | jq '.'

echo "Calibration start..."
curl -sS -X POST "$BASE/api/v1/calibration/start" -H 'Content-Type: application/json' -d '{"tag_mac":"AA:BB:CC:00:11:22","duration_ms":1000}' | jq '.'

echo "done"
