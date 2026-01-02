from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sqlite3

from app.db.database import get_db_path
from app.db.persistence import get_persistence


class SettingItem(BaseModel):
    key: str
    value: str


router = APIRouter()


def _ensure_settings_table(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at_ms INTEGER
        )"""
    )
    conn.commit()


@router.get("/settings")
def list_settings():
    db = get_db_path()
    conn = sqlite3.connect(db)
    _ensure_settings_table(conn)
    cur = conn.execute("SELECT key,value FROM settings")
    items = [{"key": r[0], "value": r[1]} for r in cur.fetchall()]
    conn.close()
    return {"settings": items}


@router.put("/settings")
def put_setting(item: SettingItem):
    # prevent saving settings while system is LIVE
    p = get_persistence()
    state = p.get_setting('system.state', 'SETUP')
    if state == 'LIVE':
        raise HTTPException(status_code=409, detail={'code': 'STATE_BLOCKED', 'message': 'Cannot change settings while LIVE'})

    db = get_db_path()
    conn = sqlite3.connect(db)
    _ensure_settings_table(conn)
    ts = int(__import__('time').time() * 1000)
    conn.execute("INSERT OR REPLACE INTO settings(key,value,updated_at_ms) VALUES(?,?,?)", (item.key, item.value, ts))
    conn.commit()
    conn.close()
    return {"ok": True}
# /settings routes
