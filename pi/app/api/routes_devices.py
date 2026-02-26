from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import os
import re

from app.db.persistence import get_persistence
from app.db import connect_db
import json, time
from app.bridge_client import call_bridge, BridgeError


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
    anchor_index: Optional[int] = None
    antenna_delay: Optional[int] = None
    range_scale: Optional[float] = None
    range_offset_cm: Optional[float] = None


class DeviceProvision(BaseModel):
    wifi_ssid: Optional[str] = None
    wifi_pass: Optional[str] = None
    mqtt_host: Optional[str] = None
    mqtt_port: Optional[int] = None
    alias: Optional[str] = None
    apply: Optional[bool] = True
    reboot: Optional[bool] = True
    timeout_ms: Optional[int] = 8000


class TagMapRequest(BaseModel):
    tag_id: Optional[str] = None


def _normalize_mac(mac: str) -> str:
    if not mac:
        return ""
    return re.sub(r"[^0-9A-Fa-f]", "", mac).upper()


def _format_mac_colon(mac_norm: str) -> str:
    if not mac_norm or len(mac_norm) != 12:
        return mac_norm
    return ":".join([mac_norm[i:i+2] for i in range(0, 12, 2)])


def _normalize_tag_id(tag_id: Optional[str]) -> str:
    raw = str(tag_id or "").strip()
    if not raw:
        return "T1"
    if raw[0] in ("T", "t"):
        raw = raw[1:]
    try:
        tid = int(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid tag_id")
    if tid < 0 or tid > 7:
        raise HTTPException(status_code=400, detail="tag_id out of range (0-7)")
    return f"T{tid}"


def _parse_bool_setting(raw, default=False) -> bool:
    if raw is None:
        return bool(default)
    if isinstance(raw, bool):
        return raw
    val = str(raw).strip().lower()
    if val in {"1", "true", "yes", "on"}:
        return True
    if val in {"0", "false", "no", "off", ""}:
        return False
    return bool(default)


def _parse_optional_pin_setting(raw, default=None):
    if raw is None:
        return default
    text = str(raw).strip()
    if text == "":
        return default
    if text.lower() in {"none", "null", "off", "disabled"}:
        return None
    try:
        pin = int(text)
    except Exception:
        return default
    if pin < 0:
        return None
    return pin


def _parse_int_setting(raw, default):
    try:
        return int(raw)
    except Exception:
        return int(default)


def _collect_anchor_macs() -> set:
    anchors = set()
    p = get_persistence()
    try:
        for dev in p.list_devices():
            role = (dev.get("role") or "").upper()
            if role == "ANCHOR":
                mac = _normalize_mac(dev.get("mac"))
                if mac:
                    anchors.add(mac)
    except Exception:
        pass
    db = connect_db()
    try:
        try:
            rows = db.execute("SELECT mac FROM anchor_positions").fetchall()
            for r in rows:
                mac = _normalize_mac(r["mac"])
                if mac:
                    anchors.add(mac)
        except Exception:
            pass
        try:
            rows = db.execute("SELECT mac FROM anchors").fetchall()
            for r in rows:
                mac = _normalize_mac(r["mac"])
                if mac:
                    anchors.add(mac)
        except Exception:
            pass
    finally:
        db.close()
    return anchors

def _ensure_anchor_index(mac_norm: str, p) -> Optional[int]:
    try:
        cur = p.get_device_setting(mac_norm, "anchor_index", "")
        if cur != "":
            idx = int(cur)
            if 0 <= idx <= 7:
                return idx
    except Exception:
        pass

    used = set()
    try:
        rows = p.list_device_settings_by_key("anchor_index")
        for r in rows:
            try:
                used.add(int(r.get("value")))
            except Exception:
                pass
    except Exception:
        pass

    for i in range(8):
        if i not in used:
            try:
                p.upsert_device_setting(mac_norm, "anchor_index", str(i))
            except Exception:
                pass
            return i
    return None


@router.get("/devices")
def list_devices():
    p = get_persistence()
    return {"devices": p.list_devices()}


@router.put("/devices/{mac}")
def upsert_device(mac: str, body: DeviceIn, request: Request):
    mac_norm = _normalize_mac(body.mac or mac)
    if not mac_norm:
        raise HTTPException(status_code=400, detail="invalid mac")
    body.mac = mac_norm
    p = get_persistence()
    p.upsert_device(body.dict())
    published = False
    if body.alias is not None:
        body.alias = body.alias[:10]
        mc = getattr(request.app.state, "mqtt_client", None)
        client = getattr(mc, "_client", None) if mc else None
        if client:
            payload = {
                "type": "cmd",
                "cmd": "apply_settings",
                "cmd_id": f"alias_{int(time.time()*1000)}",
                "settings": {"alias": body.alias},
            }
            topic = f"dev/{mac_norm}/cmd"
            client.publish(topic, json.dumps(payload), qos=1)
            published = True
    return {"ok": True, "alias_published": published}


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
        alias = body.alias[:10]
        settings["alias"] = alias
        try:
            p = get_persistence()
            p.upsert_device({"mac": mac_norm, "alias": alias})
        except Exception:
            pass
    if body.anchor_index is not None:
        if body.anchor_index < 0 or body.anchor_index > 7:
            raise HTTPException(status_code=400, detail="anchor_index out of range (0-7)")
        settings["anchor_index"] = body.anchor_index
        try:
            p = get_persistence()
            p.upsert_device_setting(mac_norm, "anchor_index", str(body.anchor_index))
        except Exception:
            pass
    else:
        try:
            p = get_persistence()
            dev = p.get_device(mac_norm)
            role = (dev.get("role") or "").upper() if dev else ""
            if role == "ANCHOR" or mac_norm in _collect_anchor_macs():
                idx = _ensure_anchor_index(mac_norm, p)
                if idx is not None:
                    settings["anchor_index"] = idx
        except Exception:
            pass
    if body.antenna_delay is not None:
        settings["antenna_delay"] = int(body.antenna_delay)
        try:
            p = get_persistence()
            p.upsert_device_setting(mac_norm, "antenna_delay", str(int(body.antenna_delay)))
        except Exception:
            pass
    if body.range_scale is not None:
        if body.range_scale <= 0:
            raise HTTPException(status_code=400, detail="range_scale must be > 0")
        settings["range_scale"] = float(body.range_scale)
        try:
            p = get_persistence()
            p.upsert_device_setting(mac_norm, "range_scale", str(float(body.range_scale)))
        except Exception:
            pass
    if body.range_offset_cm is not None:
        settings["range_offset_cm"] = float(body.range_offset_cm)
        try:
            p = get_persistence()
            p.upsert_device_setting(mac_norm, "range_offset_cm", str(float(body.range_offset_cm)))
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


@router.post("/devices/{mac}/provision")
def provision_device(mac: str, body: DeviceProvision, request: Request):
    mac_norm = _normalize_mac(mac)
    if not mac_norm:
        raise HTTPException(status_code=400, detail="invalid mac")
    p = get_persistence()
    ssid = body.wifi_ssid if body.wifi_ssid is not None else (p.get_setting("wifi.ssid", "") or "")
    wpass = body.wifi_pass if body.wifi_pass is not None else (p.get_setting("wifi.pass", "") or "")
    host = body.mqtt_host if body.mqtt_host is not None else (p.get_setting("mqtt.host", "") or "")
    port = body.mqtt_port if body.mqtt_port is not None else int(p.get_setting("mqtt.port", 1883) or 1883)
    if not ssid or not host or not port:
        raise HTTPException(status_code=400, detail="wifi/mqtt defaults missing")

    alias = (body.alias or "").strip()
    if alias:
        alias = alias[:10]
        try:
            p.upsert_device({"mac": mac_norm, "alias": alias})
        except Exception:
            pass

    bridge_port = (p.get_setting("provision.bridge_port", "") or "").strip()
    if not bridge_port:
        bridge_port = "/dev/serial0" if os.path.exists("/dev/serial0") else "/dev/ttyUSB0"
    bridge_baud = _parse_int_setting(p.get_setting("provision.bridge_baud", 115200) or 115200, 115200)
    token = p.get_setting("provision.token", "changeme") or "changeme"

    raw_gpio_enabled = p.get_setting("provision.bridge_gpio_enabled", "")
    if str(raw_gpio_enabled).strip() == "":
        bridge_gpio_enabled = bridge_port == "/dev/serial0"
    else:
        bridge_gpio_enabled = _parse_bool_setting(raw_gpio_enabled, default=False)
    bridge_reset_pin = None
    bridge_boot_pin = None
    bridge_auto_reset = False
    bridge_reset_active_low = True
    bridge_boot_active_low = True
    if bridge_gpio_enabled:
        bridge_reset_pin = _parse_optional_pin_setting(
            p.get_setting("provision.bridge_reset_pin", 17 if bridge_port == "/dev/serial0" else None),
            default=17 if bridge_port == "/dev/serial0" else None,
        )
        bridge_boot_pin = _parse_optional_pin_setting(
            p.get_setting("provision.bridge_boot_pin", 27 if bridge_port == "/dev/serial0" else None),
            default=27 if bridge_port == "/dev/serial0" else None,
        )
        bridge_auto_reset = _parse_bool_setting(
            p.get_setting("provision.bridge_auto_reset", "1" if bridge_port == "/dev/serial0" else "0"),
            default=(bridge_port == "/dev/serial0"),
        )
        bridge_reset_active_low = _parse_bool_setting(
            p.get_setting("provision.bridge_reset_active_low", "1"), default=True
        )
        bridge_boot_active_low = _parse_bool_setting(
            p.get_setting("provision.bridge_boot_active_low", "1"), default=True
        )

    payload = {
        "op": "provision_write",
        "device_id": _format_mac_colon(mac_norm),
        "auth": {"token": token},
        "cfg": {
            "wifi": {"ssid": ssid, "pass": wpass},
            "mqtt": {"host": host, "port": int(port)},
        },
        "apply": True if body.apply is None else bool(body.apply),
        "reboot": True if body.reboot is None else bool(body.reboot),
        "timeout_ms": int(body.timeout_ms or 8000),
    }
    timeout_ms = int(body.timeout_ms or 8000)
    steps = 3  # provision_write retries
    if payload["apply"]:
        steps += 2
    if payload["reboot"]:
        steps += 2
    timeout_s = max(5.0, (timeout_ms / 1000.0) * steps + 2.0)
    try:
        resp = call_bridge(
            bridge_port,
            bridge_baud,
            payload,
            timeout_s=timeout_s,
            reset_pin=bridge_reset_pin,
            boot_pin=bridge_boot_pin,
            reset_active_low=bridge_reset_active_low,
            boot_active_low=bridge_boot_active_low,
            auto_reset=bridge_auto_reset,
        )
    except BridgeError as e:
        # Graceful fallback when GPIO pin control is configured but backend is missing.
        msg = str(e).lower()
        can_retry_without_gpio = (
            (bridge_reset_pin is not None or bridge_boot_pin is not None or bridge_auto_reset)
            and (
                "no backend found" in msg
                or "gpio bridge support unavailable" in msg
                or "not importable" in msg
                or "module 'provision_bridge_pi_gpio" in msg
            )
        )
        if can_retry_without_gpio:
            try:
                resp = call_bridge(bridge_port, bridge_baud, payload, timeout_s=timeout_s)
            except BridgeError as e2:
                raise HTTPException(status_code=503, detail=str(e2))
        else:
            raise HTTPException(status_code=503, detail=str(e))
    if not resp:
        raise HTTPException(status_code=504, detail="bridge timeout")
    if resp.get("status") == "error":
        code = (resp.get("err") or {}).get("code") or "BRIDGE_ERROR"
        status = 409 if code == "BUSY" else 502
        raise HTTPException(status_code=status, detail=resp)
    return {"ok": True, "bridge": resp, "mac": mac_norm, "alias": alias or None}


@router.post("/devices/{mac}/tag-map")
def apply_tag_map_to_anchors(mac: str, body: TagMapRequest, request: Request):
    mac_norm = _normalize_mac(mac)
    if not mac_norm:
        raise HTTPException(status_code=400, detail="invalid mac")
    tag_id = _normalize_tag_id(body.tag_id)
    tag_mac = _format_mac_colon(mac_norm)
    anchors = _collect_anchor_macs()
    if not anchors:
        raise HTTPException(status_code=404, detail="no anchors found")
    mc = getattr(request.app.state, "mqtt_client", None)
    client = getattr(mc, "_client", None) if mc else None
    if not client:
        raise HTTPException(status_code=503, detail="mqtt client not available")
    ts = int(time.time() * 1000)
    payload_base = {
        "type": "cmd",
        "cmd": "apply_settings",
        "settings": {"tag_map": {tag_id: tag_mac}},
    }
    for anchor in anchors:
        payload = payload_base.copy()
        payload["cmd_id"] = f"tagmap_{tag_id}_{ts}_{anchor[-4:]}"
        client.publish(f"dev/{anchor}/cmd", json.dumps(payload), qos=1)
    return {"published": len(anchors), "tag_id": tag_id, "tag_mac": tag_mac, "anchors": sorted(anchors)}
