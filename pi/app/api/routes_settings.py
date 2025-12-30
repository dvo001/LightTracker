from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sqlite3

from app.db.database import get_db_path


class SettingItem(BaseModel):
    key: str
    value: str


router = APIRouter()


@router.get("/settings")
def list_settings():
    db = get_db_path()
    conn = sqlite3.connect(db)
    cur = conn.execute("SELECT key,value FROM settings")
    items = [{"key": r[0], "value": r[1]} for r in cur.fetchall()]
    conn.close()
    return {"settings": items}


@router.put("/settings")
def put_setting(item: SettingItem):
    db = get_db_path()
    conn = sqlite3.connect(db)
    ts = int(__import__('time').time() * 1000)
    conn.execute("INSERT OR REPLACE INTO settings(key,value,updated_at_ms) VALUES(?,?,?)", (item.key, item.value, ts))
    conn.commit()
    conn.close()
    return {"ok": True}
# /settings routes
