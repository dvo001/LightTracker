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


# Offer a module-level singleton
_persistence = Persistence()


def get_persistence() -> Persistence:
    return _persistence
# Persistence layer CRUD
