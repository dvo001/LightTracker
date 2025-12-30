import os
import sqlite3
from pathlib import Path
from typing import Optional

from app import config


def _ensure_dir(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)


def get_db_path() -> str:
    return os.environ.get("PI_DB_PATH") or config.DB_PATH


def connect() -> sqlite3.Connection:
    db_path = Path(get_db_path())
    _ensure_dir(db_path)
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    # PRAGMA as required
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def close(conn: Optional[sqlite3.Connection]):
    if conn:
        conn.close()
# SQLite connection helpers
