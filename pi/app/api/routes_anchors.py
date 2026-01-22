from fastapi import APIRouter, HTTPException, Request
from ..db import connect_db
from pydantic import BaseModel
from typing import Optional
import json
import time
from app.core.state_manager import StateManager
from app.db.persistence import get_persistence
from app.core.anchor_positions import load_anchor_offsets

router = APIRouter()


class AnchorPos(BaseModel):
    mac: str
    x_cm: int
    y_cm: int
    z_cm: int
    alias: Optional[str] = None


def _normalize_mac(mac: str) -> str:
    import re
    if not mac:
        return ""
    return re.sub(r"[^0-9A-Fa-f]", "", mac).upper()


def _mac_variants(mac: str) -> list[str]:
    raw = (mac or "").strip()
    norm = _normalize_mac(raw)
    variants = []
    for v in (raw, norm):
        if v and v not in variants:
            variants.append(v)
    if len(norm) == 12:
        colon = ":".join([norm[i:i+2] for i in range(0, 12, 2)])
        if colon not in variants:
            variants.append(colon)
    return variants


@router.get('/anchors')
def list_anchors():
    alias_map = {}
    idx_map = {}
    try:
        p = get_persistence()
        for d in p.list_devices():
            if d.get("alias") and d.get("mac"):
                alias_map[_normalize_mac(d.get("mac"))] = d.get("alias")
            mac_norm = _normalize_mac(d.get("mac"))
            if mac_norm:
                try:
                    idx = p.get_device_setting(mac_norm, "anchor_index", "")
                    if idx != "":
                        idx_map[mac_norm] = int(idx)
                except Exception:
                    pass
    except Exception:
        pass
    db = connect_db()
    try:
        offsets = load_anchor_offsets(db)
        try:
            rows = db.execute("SELECT mac, alias FROM anchors WHERE alias IS NOT NULL AND alias != ''").fetchall()
            for r in rows:
                nm = _normalize_mac(r["mac"])
                if nm and nm not in alias_map:
                    alias_map[nm] = r["alias"]
        except Exception:
            pass
        # prefer anchor_positions table if present
        try:
            rows = db.execute('SELECT mac, x_cm, y_cm, z_cm, updated_at_ms FROM anchor_positions').fetchall()
            anchors = []
            for r in rows:
                dx, dy, dz = offsets.get(r["mac"], (0.0, 0.0, 0.0))
                anchors.append(
                    {
                        'mac': r['mac'],
                        'alias': alias_map.get(_normalize_mac(r['mac'])),
                        'anchor_index': idx_map.get(_normalize_mac(r['mac'])),
                        'position_cm': {'x': r['x_cm'] + dx, 'y': r['y_cm'] + dy, 'z': r['z_cm'] + dz},
                        'position_base_cm': {'x': r['x_cm'], 'y': r['y_cm'], 'z': r['z_cm']},
                        'offset_cm': {'x': dx, 'y': dy, 'z': dz},
                        'last_seen_at_ms': r['updated_at_ms']
                    }
                )
        except Exception:
            # fallback to anchors table
            rows = db.execute('SELECT mac, alias, pos_x_cm, pos_y_cm, pos_z_cm, last_seen_at_ms FROM anchors').fetchall()
            anchors = []
            for r in rows:
                dx, dy, dz = offsets.get(r["mac"], (0.0, 0.0, 0.0))
                anchors.append(
                    {
                        'mac': r['mac'],
                        'alias': alias_map.get(_normalize_mac(r['mac'])) or (r['alias'] if 'alias' in r.keys() else None),
                        'anchor_index': idx_map.get(_normalize_mac(r['mac'])),
                        'position_cm': {'x': r['pos_x_cm'] + dx, 'y': r['pos_y_cm'] + dy, 'z': r['pos_z_cm'] + dz},
                        'position_base_cm': {'x': r['pos_x_cm'], 'y': r['pos_y_cm'], 'z': r['pos_z_cm']},
                        'offset_cm': {'x': dx, 'y': dy, 'z': dz},
                        'last_seen_at_ms': r['last_seen_at_ms'] if 'last_seen_at_ms' in r.keys() else None
                    }
                )
    finally:
        db.close()
    return {'anchors': anchors}


@router.get('/anchors/{mac}')
def get_anchor(mac: str):
    db = connect_db()
    try:
        offsets = load_anchor_offsets(db)
        alias = None
        try:
            dev = get_persistence().get_device(_normalize_mac(mac))
            if dev and dev.get("alias"):
                alias = dev.get("alias")
        except Exception:
            pass
        if not alias:
            try:
                row = db.execute("SELECT alias FROM anchors WHERE mac=? AND alias IS NOT NULL AND alias != ''", (mac,)).fetchone()
                if row and row["alias"]:
                    alias = row["alias"]
            except Exception:
                pass
        row = db.execute('SELECT mac, x_cm, y_cm, z_cm, updated_at_ms FROM anchor_positions WHERE mac=?', (mac,)).fetchone()
        if row:
            dx, dy, dz = offsets.get(row["mac"], (0.0, 0.0, 0.0))
            a = {
                'mac': row['mac'],
                'alias': alias,
                'position_cm': {'x': row['x_cm'] + dx, 'y': row['y_cm'] + dy, 'z': row['z_cm'] + dz},
                'position_base_cm': {'x': row['x_cm'], 'y': row['y_cm'], 'z': row['z_cm']},
                'offset_cm': {'x': dx, 'y': dy, 'z': dz},
                'last_seen_at_ms': row['updated_at_ms']
            }
        else:
            row = db.execute('SELECT mac, alias, pos_x_cm, pos_y_cm, pos_z_cm, last_seen_at_ms FROM anchors WHERE mac=?', (mac,)).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail='not found')
            dx, dy, dz = offsets.get(row["mac"], (0.0, 0.0, 0.0))
            a = {
                'mac': row['mac'],
                'alias': alias or row.get('alias'),
                'position_cm': {'x': row['pos_x_cm'] + dx, 'y': row['pos_y_cm'] + dy, 'z': row['pos_z_cm'] + dz},
                'position_base_cm': {'x': row['pos_x_cm'], 'y': row['pos_y_cm'], 'z': row['pos_z_cm']},
                'offset_cm': {'x': dx, 'y': dy, 'z': dz},
                'last_seen_at_ms': row.get('last_seen_at_ms')
            }
    finally:
        db.close()
    return a


@router.post('/anchors/position')
def upsert_anchor(pos: AnchorPos, request: Request):
    sm = StateManager()
    if sm.get_state() == 'LIVE':
        raise HTTPException(status_code=409, detail={'code': 'LIVE_GUARD', 'message': 'Anchor position changes blocked in LIVE'})
    db = connect_db()
    ts = int(time.time() * 1000)
    try:
        db.execute('CREATE TABLE IF NOT EXISTS anchor_positions (mac TEXT PRIMARY KEY, x_cm INTEGER, y_cm INTEGER, z_cm INTEGER, updated_at_ms INTEGER)')
        db.execute('INSERT OR REPLACE INTO anchor_positions(mac,x_cm,y_cm,z_cm,updated_at_ms) VALUES(?,?,?,?,?)', (pos.mac, pos.x_cm, pos.y_cm, pos.z_cm, ts))
        db.commit()
    finally:
        db.close()
    try:
        get_persistence().invalidate_calibrations(ts)
        StateManager().set_state('SETUP')  # ensure live guarded
    except Exception:
        pass
    mac_norm = _normalize_mac(pos.mac)
    alias_to_send = None
    if pos.alias is not None:
        alias = pos.alias.strip()
        if alias:
            alias_to_send = alias[:10]
            try:
                get_persistence().upsert_device({"mac": mac_norm, "alias": alias_to_send})
            except Exception:
                pass
    if not alias_to_send and mac_norm:
        try:
            dev = get_persistence().get_device(mac_norm)
            if dev and dev.get("alias"):
                alias_to_send = str(dev.get("alias"))[:10]
        except Exception:
            pass
    if alias_to_send:
        mc = getattr(request.app.state, "mqtt_client", None)
        client = getattr(mc, "_client", None) if mc else None
        if client:
            payload = {
                "type": "cmd",
                "cmd": "apply_settings",
                "cmd_id": f"alias_{int(time.time()*1000)}",
                "settings": {"alias": alias_to_send},
            }
            client.publish(f"dev/{mac_norm}/cmd", json.dumps(payload), qos=1)
    return {'ok': True, 'mac': pos.mac, 'position_cm': {'x': pos.x_cm, 'y': pos.y_cm, 'z': pos.z_cm}}


@router.delete('/anchors/{mac}')
def delete_anchor(mac: str, request: Request):
    sm = StateManager()
    if sm.get_state() == 'LIVE':
        raise HTTPException(status_code=409, detail={'code': 'LIVE_GUARD', 'message': 'Anchor delete blocked in LIVE'})
    mac_norm = _normalize_mac(mac)
    if not mac_norm:
        raise HTTPException(status_code=400, detail="invalid mac")
    variants = _mac_variants(mac)
    db = connect_db()
    removed_positions = 0
    removed_anchors = 0
    try:
        if variants:
            placeholders = ",".join(["?"] * len(variants))
            cur = db.execute(f"DELETE FROM anchor_positions WHERE mac IN ({placeholders})", variants)
            removed_positions = cur.rowcount or 0
            cur = db.execute(f"DELETE FROM anchors WHERE mac IN ({placeholders})", variants)
            removed_anchors = cur.rowcount or 0
        db.execute("DELETE FROM device_settings WHERE mac=?", (mac_norm,))
        db.commit()
    finally:
        db.close()
    removed_device = False
    try:
        removed_device = get_persistence().delete_device(mac_norm)
    except Exception:
        pass
    return {
        "ok": True,
        "mac": mac_norm,
        "removed_positions": removed_positions,
        "removed_anchors": removed_anchors,
        "removed_device": removed_device,
    }
