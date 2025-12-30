from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sqlite3

from app.db.database import get_db_path


class DeviceModel(BaseModel):
    mac: str
    role: str = None
    alias: str = None
    name: str = None


router = APIRouter()


@router.get("/devices")
def list_devices():
    db = get_db_path()
    conn = sqlite3.connect(db)
    cur = conn.execute("SELECT mac,role,alias,name,ip_last,fw,status FROM devices")
    items = [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]
    conn.close()
    return {"devices": items}


@router.put("/devices/{mac}")
def put_device(mac: str, body: DeviceModel):
    db = get_db_path()
    conn = sqlite3.connect(db)
    ts = int(__import__('time').time() * 1000)
    conn.execute("INSERT OR REPLACE INTO devices(mac,role,alias,name,first_seen_at_ms,last_seen_at_ms,status) VALUES(?,?,?,?,?,?,?)", (mac, body.role, body.alias, body.name, ts, ts, 'UNKNOWN'))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/devices/{mac}")
def delete_device(mac: str):
    db = get_db_path()
    conn = sqlite3.connect(db)
    cur = conn.execute("DELETE FROM devices WHERE mac=?", (mac,))
    conn.commit()
    conn.close()
    return {"deleted": cur.rowcount}
# /devices routes
