import json
import threading
from typing import Any, Dict, List, Optional

from . import connect_db

_lock = threading.Lock()
_singleton = None


class Persistence:
    def __init__(self):
        self._ensure_tables()

    def _ensure_tables(self):
        db = connect_db()
        try:
            db.execute(
                """CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at_ms INTEGER
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS fixtures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    profile_key TEXT,
                    universe INTEGER,
                    dmx_base_addr INTEGER,
                    pos_x_cm INTEGER,
                    pos_y_cm INTEGER,
                    pos_z_cm INTEGER,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    updated_at_ms INTEGER
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS fixture_profiles (
                    profile_key TEXT PRIMARY KEY,
                    profile_json TEXT
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS anchors (
                    mac TEXT PRIMARY KEY,
                    alias TEXT,
                    pos_x_cm INTEGER,
                    pos_y_cm INTEGER,
                    pos_z_cm INTEGER,
                    last_seen_at_ms INTEGER
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS anchor_positions (
                    mac TEXT PRIMARY KEY,
                    x_cm INTEGER,
                    y_cm INTEGER,
                    z_cm INTEGER,
                    updated_at_ms INTEGER
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS devices (
                    mac TEXT PRIMARY KEY,
                    last_seen_at_ms INTEGER
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS calibration_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag_mac TEXT,
                    started_at_ms INTEGER,
                    ended_at_ms INTEGER,
                    result TEXT,
                    invalidated_at_ms INTEGER,
                    params_json TEXT,
                    summary_json TEXT,
                    status TEXT,
                    committed_at_ms INTEGER,
                    discarded_at_ms INTEGER
                )"""
            )
            db.commit()
        finally:
            db.close()

    # Settings
    def get_setting(self, key: str, default: Optional[Any] = None) -> Any:
        db = connect_db()
        try:
            row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            if not row:
                return default
            return row["value"]
        finally:
            db.close()

    # Fixture profiles
    def list_fixture_profiles(self) -> List[Dict[str, Any]]:
        db = connect_db()
        try:
            rows = db.execute("SELECT profile_key, profile_json FROM fixture_profiles").fetchall()
            return [dict(r) for r in rows]
        finally:
            db.close()

    # Fixtures
    def list_fixtures(self) -> List[Dict[str, Any]]:
        db = connect_db()
        try:
            rows = db.execute(
                "SELECT id, name, profile_key, universe, dmx_base_addr, pos_x_cm, pos_y_cm, pos_z_cm, enabled, updated_at_ms FROM fixtures"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            db.close()

    def create_fixture(self, data: Dict[str, Any]) -> int:
        db = connect_db()
        try:
            ts = int(__import__("time").time() * 1000)
            cur = db.execute(
                """INSERT INTO fixtures(name, profile_key, universe, dmx_base_addr, pos_x_cm, pos_y_cm, pos_z_cm, enabled, updated_at_ms)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    data.get("name"),
                    data.get("profile_key"),
                    data.get("universe"),
                    data.get("dmx_base_addr"),
                    data.get("pos_x_cm"),
                    data.get("pos_y_cm"),
                    data.get("pos_z_cm"),
                    1,
                    ts,
                ),
            )
            db.commit()
            return cur.lastrowid
        finally:
            db.close()

    def get_fixture(self, fid: int) -> Optional[Dict[str, Any]]:
        db = connect_db()
        try:
            row = db.execute(
                "SELECT id, name, profile_key, universe, dmx_base_addr, pos_x_cm, pos_y_cm, pos_z_cm, enabled, updated_at_ms FROM fixtures WHERE id=?",
                (fid,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            db.close()

    def update_fixture(self, fid: int, data: Dict[str, Any]) -> bool:
        if not data:
            return False
        db = connect_db()
        try:
            allowed = {"name", "profile_key", "universe", "dmx_base_addr", "pos_x_cm", "pos_y_cm", "pos_z_cm", "enabled"}
            set_parts = []
            values = []
            for k, v in data.items():
                if k not in allowed:
                    continue
                set_parts.append(f"{k}=?")
                values.append(v)
            if not set_parts:
                return False
            values.append(int(__import__("time").time() * 1000))
            values.append(fid)
            sql = f"UPDATE fixtures SET {', '.join(set_parts)}, updated_at_ms=? WHERE id=?"
            cur = db.execute(sql, values)
            db.commit()
            return cur.rowcount > 0
        finally:
            db.close()

    def delete_fixture(self, fid: int) -> bool:
        db = connect_db()
        try:
            cur = db.execute("DELETE FROM fixtures WHERE id=?", (fid,))
            db.commit()
            return cur.rowcount > 0
        finally:
            db.close()


def get_persistence() -> Persistence:
    global _singleton
    if _singleton:
        return _singleton
    with _lock:
        if not _singleton:
            _singleton = Persistence()
    return _singleton
