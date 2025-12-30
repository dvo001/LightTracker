import os
from pathlib import Path

# Default DB location under pi/data
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = str(DEFAULT_DATA_DIR / "lighttracker.db")

# MQTT defaults (can be overridden via settings table in DB later)
MQTT_HOST = os.environ.get("PI_MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("PI_MQTT_PORT", "1883"))
# Settings loader (SQLite + env overrides)
