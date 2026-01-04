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
    try:
        p = get_persistence()
        # ensure table exists (persistence does this on init)
        items = []
        db = sqlite3.connect(get_db_path())
        try:
            _ensure_settings_table(db)
            rows = db.execute("SELECT key,value FROM settings").fetchall()
            items = [{"key": r[0], "value": r[1]} for r in rows]
        finally:
            db.close()
        return {"settings": items}
    except Exception:
        # fallback raw
        db = sqlite3.connect(get_db_path())
        _ensure_settings_table(db)
        cur = db.execute("SELECT key,value FROM settings")
        items = [{"key": r[0], "value": r[1]} for r in cur.fetchall()]
        db.close()
        return {"settings": items}


@router.put("/settings")
def put_setting(item: SettingItem):
    # prevent saving settings while system is LIVE
    p = get_persistence()
    state = p.get_setting('system.state', 'SETUP')
    if state == 'LIVE':
        raise HTTPException(status_code=409, detail={'code': 'STATE_BLOCKED', 'message': 'Cannot change settings while LIVE'})

    # use persistence so the same connection path is used everywhere
    p.upsert_setting(item.key, item.value)
    return {"ok": True}
# /settings routes
