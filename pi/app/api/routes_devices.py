from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.db.persistence import get_persistence


router = APIRouter()


class DeviceIn(BaseModel):
    mac: str
    role: Optional[str] = None
    alias: Optional[str] = None
    name: Optional[str] = None
    ip_last: Optional[str] = None
    fw: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


@router.get("/devices")
def list_devices():
    p = get_persistence()
    return {"devices": p.list_devices()}


@router.put("/devices/{mac}")
def upsert_device(mac: str, body: DeviceIn):
    if mac != body.mac:
        raise HTTPException(status_code=400, detail="mac mismatch")
    p = get_persistence()
    p.upsert_device(body.dict())
    return {"ok": True}


@router.delete("/devices/{mac}")
def delete_device(mac: str):
    p = get_persistence()
    ok = p.delete_device(mac)
    if not ok:
        raise HTTPException(status_code=404, detail="not found")
    return {"deleted": True}
