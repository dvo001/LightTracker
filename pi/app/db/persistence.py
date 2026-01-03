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
                    role TEXT,
                    alias TEXT,
                    name TEXT,
                    ip_last TEXT,
                    fw TEXT,
                    first_seen_at_ms INTEGER,
                    last_seen_at_ms INTEGER,
                    status TEXT,
                    notes TEXT
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS device_settings (
                    mac TEXT,
                    key TEXT,
                    value TEXT,
                    updated_at_ms INTEGER,
                    PRIMARY KEY(mac, key)
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
            db.execute(
                """CREATE TABLE IF NOT EXISTS event_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_ms INTEGER,
                    level TEXT,
                    source TEXT,
                    event_type TEXT,
                    ref TEXT,
                    details_json TEXT
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

    def upsert_fixture_profile(self, profile_key: str, profile_json: str) -> None:
        db = connect_db()
        try:
            db.execute(
                "INSERT INTO fixture_profiles(profile_key, profile_json) VALUES(?, ?) ON CONFLICT(profile_key) DO UPDATE SET profile_json=excluded.profile_json",
                (profile_key, profile_json),
            )
            db.commit()
        finally:
            db.close()

    # OFL fixtures library
    def upsert_ofl_fixture(self, manufacturer: str, model: str, ofl_schema: str, ofl_json: str, content_hash: str) -> int:
        db = connect_db()
        try:
            ts = int(__import__("time").time() * 1000)
            cur = db.execute(
                """INSERT INTO ofl_fixtures(manufacturer, model, ofl_schema, ofl_json, content_hash, created_at_ms, updated_at_ms)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(content_hash) DO UPDATE SET
                     manufacturer=excluded.manufacturer,
                     model=excluded.model,
                     ofl_schema=excluded.ofl_schema,
                     ofl_json=excluded.ofl_json,
                     updated_at_ms=excluded.updated_at_ms""",
                (manufacturer, model, ofl_schema, ofl_json, content_hash, ts, ts),
            )
            db.commit()
            if cur.lastrowid:
                return cur.lastrowid
            row = db.execute("SELECT id FROM ofl_fixtures WHERE content_hash=?", (content_hash,)).fetchone()
            return row["id"] if row else None
        finally:
            db.close()

    def find_ofl_fixture_by_hash(self, content_hash: str):
        db = connect_db()
        try:
            row = db.execute("SELECT id, manufacturer, model, ofl_schema, ofl_json, content_hash, created_at_ms, updated_at_ms FROM ofl_fixtures WHERE content_hash=?", (content_hash,)).fetchone()
            return dict(row) if row else None
        finally:
            db.close()

    def get_ofl_fixture(self, fid: int):
        db = connect_db()
        try:
            row = db.execute("SELECT id, manufacturer, model, ofl_schema, ofl_json, content_hash, created_at_ms, updated_at_ms FROM ofl_fixtures WHERE id=?", (fid,)).fetchone()
            return dict(row) if row else None
        finally:
            db.close()

    def search_ofl_fixtures(self, q: str = None):
        db = connect_db()
        try:
            if q:
                ql = f"%{q.lower()}%"
                rows = db.execute(
                    "SELECT id, manufacturer, model, ofl_schema, ofl_json, content_hash, created_at_ms, updated_at_ms FROM ofl_fixtures WHERE lower(manufacturer) LIKE ? OR lower(model) LIKE ? ORDER BY manufacturer, model",
                    (ql, ql),
                ).fetchall()
            else:
                rows = db.execute("SELECT id, manufacturer, model, ofl_schema, ofl_json, content_hash, created_at_ms, updated_at_ms FROM ofl_fixtures ORDER BY manufacturer, model").fetchall()
            return [dict(r) for r in rows]
        finally:
            db.close()

    # Patched fixtures
    def create_patched_fixture(self, fixture_id: int, name: str, mode_name: str, universe: int, dmx_address: int, overrides_json: str = None) -> int:
        db = connect_db()
        try:
            ts = int(__import__("time").time() * 1000)
            cur = db.execute(
                """INSERT INTO patched_fixtures(fixture_id, name, mode_name, universe, dmx_address, overrides_json, created_at_ms, updated_at_ms)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (fixture_id, name, mode_name, universe, dmx_address, overrides_json, ts, ts),
            )
            db.commit()
            return cur.lastrowid
        finally:
            db.close()

    def list_patched_fixtures(self):
        db = connect_db()
        try:
            rows = db.execute("SELECT id, fixture_id, name, mode_name, universe, dmx_address, overrides_json, created_at_ms, updated_at_ms FROM patched_fixtures ORDER BY id DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            db.close()

    def get_patched_fixture(self, pid: int):
        db = connect_db()
        try:
            row = db.execute("SELECT id, fixture_id, name, mode_name, universe, dmx_address, overrides_json, created_at_ms, updated_at_ms FROM patched_fixtures WHERE id=?", (pid,)).fetchone()
            return dict(row) if row else None
        finally:
            db.close()

    # Fixtures
    def list_fixtures(self) -> List[Dict[str, Any]]:
        db = connect_db()
        try:
            rows = db.execute(
                "SELECT id, name, profile_key, universe, dmx_base_addr, pos_x_cm, pos_y_cm, pos_z_cm, pan_min_deg, pan_max_deg, tilt_min_deg, tilt_max_deg, invert_pan, invert_tilt, pan_zero_deg, tilt_zero_deg, pan_offset_deg, tilt_offset_deg, slew_pan_deg_s, slew_tilt_deg_s, enabled, updated_at_ms FROM fixtures"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            db.close()

    def create_fixture(self, data: Dict[str, Any]) -> int:
        db = connect_db()
        try:
            ts = int(__import__("time").time() * 1000)
            cur = db.execute(
                """INSERT INTO fixtures(name, profile_key, universe, dmx_base_addr, pos_x_cm, pos_y_cm, pos_z_cm,
                                        pan_min_deg, pan_max_deg, tilt_min_deg, tilt_max_deg,
                                        invert_pan, invert_tilt, pan_zero_deg, tilt_zero_deg, pan_offset_deg, tilt_offset_deg,
                                        slew_pan_deg_s, slew_tilt_deg_s,
                                        enabled, updated_at_ms)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    data.get("name"),
                    data.get("profile_key"),
                    data.get("universe"),
                    data.get("dmx_base_addr"),
                    data.get("pos_x_cm"),
                    data.get("pos_y_cm"),
                    data.get("pos_z_cm"),
                    data.get("pan_min_deg", 0),
                    data.get("pan_max_deg", 360),
                    data.get("tilt_min_deg", 0),
                    data.get("tilt_max_deg", 180),
                    data.get("invert_pan", 0),
                    data.get("invert_tilt", 0),
                    data.get("pan_zero_deg", 0),
                    data.get("tilt_zero_deg", 0),
                    data.get("pan_offset_deg", 0),
                    data.get("tilt_offset_deg", 0),
                    data.get("slew_pan_deg_s", 180),
                    data.get("slew_tilt_deg_s", 180),
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
                "SELECT id, name, profile_key, universe, dmx_base_addr, pos_x_cm, pos_y_cm, pos_z_cm, pan_min_deg, pan_max_deg, tilt_min_deg, tilt_max_deg, invert_pan, invert_tilt, pan_zero_deg, tilt_zero_deg, pan_offset_deg, tilt_offset_deg, slew_pan_deg_s, slew_tilt_deg_s, enabled, updated_at_ms FROM fixtures WHERE id=?",
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
            allowed = {"name", "profile_key", "universe", "dmx_base_addr", "pos_x_cm", "pos_y_cm", "pos_z_cm", "pan_min_deg", "pan_max_deg", "tilt_min_deg", "tilt_max_deg", "invert_pan", "invert_tilt", "pan_zero_deg", "tilt_zero_deg", "pan_offset_deg", "tilt_offset_deg", "slew_pan_deg_s", "slew_tilt_deg_s", "enabled"}
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

    # Devices
    def upsert_device(self, data: Dict[str, Any]) -> None:
        db = connect_db()
        try:
            ts = int(__import__("time").time() * 1000)
            fields = {
                "mac": data.get("mac"),
                "role": data.get("role"),
                "alias": data.get("alias"),
                "name": data.get("name"),
                "ip_last": data.get("ip_last"),
                "fw": data.get("fw"),
                "first_seen_at_ms": data.get("first_seen_at_ms", ts),
                "last_seen_at_ms": data.get("last_seen_at_ms", ts),
                "status": data.get("status"),
                "notes": data.get("notes"),
            }
            db.execute(
                """INSERT INTO devices(mac, role, alias, name, ip_last, fw, first_seen_at_ms, last_seen_at_ms, status, notes)
                   VALUES(:mac, :role, :alias, :name, :ip_last, :fw, :first_seen_at_ms, :last_seen_at_ms, :status, :notes)
                   ON CONFLICT(mac) DO UPDATE SET
                     role=excluded.role,
                     alias=COALESCE(excluded.alias, devices.alias),
                     name=COALESCE(excluded.name, devices.name),
                     ip_last=COALESCE(excluded.ip_last, devices.ip_last),
                     fw=COALESCE(excluded.fw, devices.fw),
                     last_seen_at_ms=excluded.last_seen_at_ms,
                     status=COALESCE(excluded.status, devices.status),
                     notes=COALESCE(excluded.notes, devices.notes)"""
                , fields
            )
            db.commit()
        finally:
            db.close()

    def list_devices(self) -> List[Dict[str, Any]]:
        db = connect_db()
        try:
            rows = db.execute("SELECT mac, role, alias, name, ip_last, fw, first_seen_at_ms, last_seen_at_ms, status, notes FROM devices").fetchall()
            return [dict(r) for r in rows]
        finally:
            db.close()

    def anchors_online_count(self, window_ms: int = 8000) -> int:
        now = int(__import__("time").time() * 1000)
        db = connect_db()
        try:
            rows = db.execute("SELECT role,last_seen_at_ms FROM devices WHERE role='ANCHOR'").fetchall()
            return sum(1 for r in rows if r["last_seen_at_ms"] and (now - r["last_seen_at_ms"] <= window_ms))
        finally:
            db.close()

    def delete_device(self, mac: str) -> bool:
        db = connect_db()
        try:
            cur = db.execute("DELETE FROM devices WHERE mac=?", (mac,))
            db.commit()
            return cur.rowcount > 0
        finally:
            db.close()

    # Event log
    def append_event(self, level: str, source: str, event_type: str, ref: str = None, details_json: str = None):
        db = connect_db()
        try:
            ts = int(__import__("time").time() * 1000)
            db.execute(
                "INSERT INTO event_log(ts_ms, level, source, event_type, ref, details_json) VALUES(?,?,?,?,?,?)",
                (ts, level, source, event_type, ref, details_json),
            )
            db.commit()
        finally:
            db.close()

    def upsert_setting(self, key: str, value: str):
        db = connect_db()
        try:
            ts = int(__import__("time").time() * 1000)
            db.execute(
                "INSERT INTO settings(key,value,updated_at_ms) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at_ms=excluded.updated_at_ms",
                (key, value, ts),
            )
            db.commit()
        finally:
            db.close()

    def invalidate_calibrations(self, now_ms: int):
        db = connect_db()
        try:
            db.execute("UPDATE calibration_runs SET invalidated_at_ms=? WHERE invalidated_at_ms IS NULL", (now_ms,))
            db.commit()
        finally:
            db.close()

    def list_events(self, limit: int = 200) -> List[Dict[str, Any]]:
        db = connect_db()
        try:
            rows = db.execute(
                "SELECT id, ts_ms, level, source, event_type, ref, details_json FROM event_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
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
