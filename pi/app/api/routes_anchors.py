from fastapi import APIRouter, HTTPException
from ..db import connect_db
from pydantic import BaseModel
import time

router = APIRouter()


class AnchorPos(BaseModel):
    mac: str
    x_cm: int
    y_cm: int
    z_cm: int


@router.get('/anchors')
def list_anchors():
    db = connect_db()
    try:
        # prefer anchor_positions table if present
        try:
            rows = db.execute('SELECT mac, x_cm, y_cm, z_cm, updated_at_ms FROM anchor_positions').fetchall()
            anchors = [
                {
                    'mac': r['mac'],
                    'alias': None,
                    'position_cm': {'x': r['x_cm'], 'y': r['y_cm'], 'z': r['z_cm']},
                    'last_seen_at_ms': r['updated_at_ms']
                } for r in rows
            ]
        except Exception:
            # fallback to anchors table
            rows = db.execute('SELECT mac, alias, pos_x_cm, pos_y_cm, pos_z_cm, last_seen_at_ms FROM anchors').fetchall()
            anchors = [
                {
                    'mac': r['mac'],
                    'alias': r['alias'] if 'alias' in r.keys() else None,
                    'position_cm': {'x': r['pos_x_cm'], 'y': r['pos_y_cm'], 'z': r['pos_z_cm']},
                    'last_seen_at_ms': r['last_seen_at_ms'] if 'last_seen_at_ms' in r.keys() else None
                } for r in rows
            ]
    finally:
        db.close()
    return {'anchors': anchors}


@router.get('/anchors/{mac}')
def get_anchor(mac: str):
    db = connect_db()
    try:
        row = db.execute('SELECT mac, x_cm, y_cm, z_cm, updated_at_ms FROM anchor_positions WHERE mac=?', (mac,)).fetchone()
        if row:
            a = {'mac': row['mac'], 'position_cm': {'x': row['x_cm'], 'y': row['y_cm'], 'z': row['z_cm']}, 'last_seen_at_ms': row['updated_at_ms']}
        else:
            row = db.execute('SELECT mac, alias, pos_x_cm, pos_y_cm, pos_z_cm, last_seen_at_ms FROM anchors WHERE mac=?', (mac,)).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail='not found')
            a = {'mac': row['mac'], 'alias': row.get('alias'), 'position_cm': {'x': row['pos_x_cm'], 'y': row['pos_y_cm'], 'z': row['pos_z_cm']}, 'last_seen_at_ms': row.get('last_seen_at_ms')}
    finally:
        db.close()
    return a


@router.post('/anchors/position')
def upsert_anchor(pos: AnchorPos):
    db = connect_db()
    ts = int(time.time() * 1000)
    try:
        db.execute('CREATE TABLE IF NOT EXISTS anchor_positions (mac TEXT PRIMARY KEY, x_cm INTEGER, y_cm INTEGER, z_cm INTEGER, updated_at_ms INTEGER)')
        db.execute('INSERT OR REPLACE INTO anchor_positions(mac,x_cm,y_cm,z_cm,updated_at_ms) VALUES(?,?,?,?,?)', (pos.mac, pos.x_cm, pos.y_cm, pos.z_cm, ts))
        db.commit()
    finally:
        db.close()
    return {'ok': True, 'mac': pos.mac, 'position_cm': {'x': pos.x_cm, 'y': pos.y_cm, 'z': pos.z_cm}}

