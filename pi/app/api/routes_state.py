from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sqlite3

from app.db.database import get_db_path


class StateResponse(BaseModel):
    system_state: str
    mqtt_ok: bool
    anchors_online: int


router = APIRouter()


@router.get("/state", response_model=StateResponse)
def get_state():
    db = get_db_path()
    try:
        conn = sqlite3.connect(db)
        cur = conn.execute("SELECT value FROM settings WHERE key='system.state'")
        row = cur.fetchone()
        state = row[0] if row else "SETUP"
    finally:
        conn.close()
    return {"system_state": state, "mqtt_ok": False, "anchors_online": 0}


class StateUpdate(BaseModel):
    state: str


@router.post("/state")
def set_state(body: StateUpdate):
    if body.state not in ("SETUP", "SAFE"):
        raise HTTPException(status_code=409, detail={"code": "STATE_BLOCKED", "message": "Only SETUP or SAFE allowed in Phase 1"})
    db = get_db_path()
    conn = sqlite3.connect(db)
    try:
        ts = int(__import__('time').time() * 1000)
        conn.execute("INSERT OR REPLACE INTO settings(key,value,updated_at_ms) VALUES(?,?,?)", ("system.state", body.state, ts))
        conn.commit()
    finally:
        conn.close()
    return {"system_state": body.state}
# /state routes
