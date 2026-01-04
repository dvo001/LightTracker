from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import re

from app.db.persistence import get_persistence
import json, time


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


class DeviceConfig(BaseModel):
    wifi_ssid: Optional[str] = None
    wifi_pass: Optional[str] = None
    mqtt_host: Optional[str] = None
    mqtt_port: Optional[int] = None
    batch_period_ms: Optional[int] = None
    heartbeat_ms: Optional[int] = None
    alias: Optional[str] = None


def _normalize_mac(mac: str) -> str:
    if not mac:
        return ""
    return re.sub(r"[^0-9A-Fa-f]", "", mac).upper()


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


@router.post("/devices/{mac}/apply-settings")
def apply_device_settings(mac: str, body: DeviceConfig, request: Request):
    mac_norm = _normalize_mac(mac)
    if not mac_norm:
        raise HTTPException(status_code=400, detail="invalid mac")
    mc = getattr(request.app.state, "mqtt_client", None)
    client = getattr(mc, "_client", None) if mc else None
    if not client:
        raise HTTPException(status_code=503, detail="mqtt client not available")
    settings = {}
    if body.wifi_ssid is not None:
        settings["ssid"] = body.wifi_ssid
    if body.wifi_pass is not None:
        settings["pass"] = body.wifi_pass
    if body.mqtt_host is not None:
        settings["mqtt_host"] = body.mqtt_host
    if body.mqtt_port is not None:
        settings["mqtt_port"] = body.mqtt_port
    if body.batch_period_ms is not None:
        settings["batch_period_ms"] = body.batch_period_ms
    if body.heartbeat_ms is not None:
        settings["heartbeat_ms"] = body.heartbeat_ms
    if body.alias is not None:
        settings["alias"] = body.alias
        try:
            p = get_persistence()
            p.upsert_device({"mac": mac_norm, "alias": body.alias})
        except Exception:
            pass
    if not settings:
        raise HTTPException(status_code=400, detail="no settings provided")
    payload = {
        "type": "cmd",
        "cmd": "apply_settings",
        "cmd_id": f"cfg_{int(time.time()*1000)}",
        "settings": settings,
    }
    topic = f"dev/{mac_norm}/cmd"
    client.publish(topic, json.dumps(payload), qos=1)
    return {"published": True, "topic": topic, "payload": payload}
