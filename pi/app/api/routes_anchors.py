from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.persistence import get_persistence

router = APIRouter()


class AnchorPos(BaseModel):
    mac: str
    x_cm: int
    y_cm: int
    z_cm: int


@router.post('/anchors/position')
def upsert_anchor(pos: AnchorPos):
    p = get_persistence()
    # block changes while LIVE
    state = p.get_setting('system.state', 'SETUP')
    if state == 'LIVE':
        raise HTTPException(status_code=409, detail={"code": "STATE_BLOCKED", "message": "Updating anchor positions is blocked while system is LIVE"})

    # upsert anchor position
    conn = __import__('sqlite3').connect(__import__('os').environ.get('PI_DB_PATH') or __import__('app').config.DB_PATH)
    ts = int(__import__('time').time() * 1000)
    conn.execute("INSERT OR REPLACE INTO anchor_positions(mac,x_cm,y_cm,z_cm,updated_at_ms) VALUES(?,?,?,?,?)", (pos.mac, pos.x_cm, pos.y_cm, pos.z_cm, ts))
    conn.commit()
    conn.close()
    # invalidate calibrations
    p.invalidate_calibration_runs(ts)
    p.insert_event('WARN', 'calibration', 'calibration_invalidated', pos.mac, '')
    return {'ok': True}
# /anchors routes
