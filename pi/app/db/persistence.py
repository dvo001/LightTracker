import os
import sqlite3
import time
from pathlib import Path
from typing import List

from app.db.database import connect


class Persistence:
    def __init__(self):
        self.migrations_path = Path(__file__).parent / "migrations"

    def migrate(self):
        conn = connect()
        try:
            self._ensure_schema_migrations(conn)
            applied = self._applied_versions(conn)
            sql_files = sorted(self.migrations_path.glob("*.sql"))
            for f in sql_files:
                version = f.stem
                if version in applied:
                    continue
                self._apply_migration(conn, f)
        finally:
            conn.close()

    def _ensure_schema_migrations(self, conn: sqlite3.Connection):
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                name TEXT,
                applied_at_ms INTEGER
            )
            """
        )
        conn.commit()

    def _applied_versions(self, conn: sqlite3.Connection) -> List[str]:
        cur = conn.execute("SELECT version FROM schema_migrations")
        return [r[0] for r in cur.fetchall()]

    def _apply_migration(self, conn: sqlite3.Connection, sql_path: Path):
        sql = sql_path.read_text()
        try:
            conn.executescript(sql)
            ts = int(time.time() * 1000)
            conn.execute(
                "INSERT INTO schema_migrations(version,name,applied_at_ms) VALUES(?,?,?)",
                (sql_path.stem, sql_path.name, ts),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # lightweight helpers
    def insert_event(self, level: str, source: str, event_type: str, ref: str, details_json: str):
        conn = connect()
        try:
            ts = int(time.time() * 1000)
            conn.execute(
                "INSERT INTO event_log(ts_ms,level,source,event_type,ref,details_json) VALUES(?,?,?,?,?,?)",
                (ts, level, source, event_type, ref, details_json),
            )
            conn.commit()
        finally:
            conn.close()

    def upsert_device(self, mac: str, role: str = None, alias: str = None, name: str = None, ip: str = None, fw: str = None, status: str = None, ts_ms: int = None):
        conn = connect()
        try:
            now = int(time.time() * 1000)
            ts_ms = ts_ms or now
            cur = conn.execute("SELECT first_seen_at_ms FROM devices WHERE mac=?", (mac,))
            row = cur.fetchone()
            if row is None:
                first_seen = ts_ms
            else:
                first_seen = row[0]
            conn.execute(
                "REPLACE INTO devices(mac, role, alias, name, ip_last, fw, first_seen_at_ms, last_seen_at_ms, status) VALUES(?,?,?,?,?,?,?,?,?)",
                (mac, role, alias, name, ip, fw, first_seen, ts_ms, status),
            )
            conn.commit()
        finally:
            conn.close()

    def get_setting(self, key: str, default: str = None) -> str:
        conn = connect()
        try:
            cur = conn.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = cur.fetchone()
            return row[0] if row else default
        finally:
            conn.close()

    def get_anchor_positions(self) -> dict:
        conn = connect()
        try:
            cur = conn.execute("SELECT mac,x_cm,y_cm,z_cm FROM anchor_positions")
            out = {r[0]: (r[1], r[2], r[3]) for r in cur.fetchall()}
            return out
        finally:
            conn.close()

    # Fixtures CRUD
    def create_fixture(self, data: dict) -> int:
        conn = connect()
        try:
            ts = int(time.time() * 1000)
            cols = [
                'name','universe','dmx_base_addr','profile_key','pos_x_cm','pos_y_cm','pos_z_cm',
                'pan_min_deg','pan_max_deg','tilt_min_deg','tilt_max_deg','invert_pan','invert_tilt',
                'pan_zero_deg','tilt_zero_deg','pan_offset_deg','tilt_offset_deg','slew_pan_deg_s','slew_tilt_deg_s','is_enabled','updated_at_ms'
            ]
            vals = [data.get(c) for c in cols[:-1]] + [ts]
            q = f"INSERT INTO fixtures({','.join(cols)}) VALUES({','.join(['?']*len(cols))})"
            cur = conn.execute(q, vals)
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def list_fixtures(self) -> list:
        conn = connect()
        try:
            cur = conn.execute("SELECT * FROM fixtures")
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            conn.close()

    def get_fixture(self, fid: int) -> dict:
        conn = connect()
        try:
            cur = conn.execute("SELECT * FROM fixtures WHERE id=?", (fid,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [c[0] for c in cur.description]
            return dict(zip(cols, row))
        finally:
            conn.close()

    def update_fixture(self, fid: int, data: dict) -> bool:
        conn = connect()
        try:
            ts = int(time.time() * 1000)
            keys = [k for k in data.keys()]
            if not keys:
                return False
            set_clause = ",".join([f"{k}=?" for k in keys]) + ",updated_at_ms=?"
            vals = [data[k] for k in keys] + [ts, fid]
            conn.execute(f"UPDATE fixtures SET {set_clause} WHERE id=?", vals)
            conn.commit()
            return True
        finally:
            conn.close()

    def delete_fixture(self, fid: int) -> bool:
        conn = connect()
        try:
            cur = conn.execute("DELETE FROM fixtures WHERE id=?", (fid,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def list_fixture_profiles(self) -> list:
        conn = connect()
        try:
            cur = conn.execute("SELECT profile_key, profile_json, updated_at_ms FROM fixture_profiles")
            return [{"profile_key": r[0], "profile_json": r[1], "updated_at_ms": r[2]} for r in cur.fetchall()]
        finally:
            conn.close()

    # Calibration runs CRUD
    def create_calibration_run(self, tag_mac: str, params_json: str, started_at_ms: int) -> int:
        conn = connect()
        try:
            cur = conn.execute(
                "INSERT INTO calibration_runs(tag_mac, started_at_ms, params_json) VALUES(?,?,?)",
                (tag_mac, started_at_ms, params_json),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def finish_calibration_run(self, run_id: int, result: str, ended_at_ms: int, summary_json: str = None, invalidated_at_ms: int = None):
        conn = connect()
        try:
            conn.execute(
                "UPDATE calibration_runs SET result=?, ended_at_ms=?, summary_json=?, invalidated_at_ms=? WHERE id=?",
                (result, ended_at_ms, summary_json, invalidated_at_ms, run_id),
            )
            conn.commit()
        finally:
            conn.close()

    def abort_calibration_run(self, run_id: int, ended_at_ms: int):
        conn = connect()
        try:
            conn.execute("UPDATE calibration_runs SET result='ABORTED', ended_at_ms=? WHERE id=?", (ended_at_ms, run_id))
            conn.commit()
        finally:
            conn.close()

    def list_calibration_runs(self, tag_mac: str = None) -> list:
        conn = connect()
        try:
            if tag_mac:
                cur = conn.execute("SELECT * FROM calibration_runs WHERE tag_mac=? ORDER BY started_at_ms DESC", (tag_mac,))
            else:
                cur = conn.execute("SELECT * FROM calibration_runs ORDER BY started_at_ms DESC")
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            conn.close()

    def get_calibration_run(self, run_id: int) -> dict:
        conn = connect()
        try:
            cur = conn.execute("SELECT * FROM calibration_runs WHERE id=?", (run_id,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [c[0] for c in cur.description]
            return dict(zip(cols, row))
        finally:
            conn.close()

    def invalidate_calibration_runs(self, now_ms: int):
        conn = connect()
        try:
            # set invalidated_at_ms for runs that are OK and not already invalidated
            conn.execute("UPDATE calibration_runs SET invalidated_at_ms=? WHERE result='OK' AND (invalidated_at_ms IS NULL)", (now_ms,))
            conn.commit()
        finally:
            conn.close()


# Offer a module-level singleton
_persistence = Persistence()


def get_persistence() -> Persistence:
    return _persistence
# Persistence layer CRUD
