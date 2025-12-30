from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.dmx.dmx_engine import DMXEngine
from app.db.persistence import get_persistence
from typing import Tuple

router = APIRouter()


class AimRequest(BaseModel):
    target_cm: Tuple[int, int, int]
    duration_ms: int = 5000


@router.post("/dmx/aim")
def aim(req: AimRequest):
    p = get_persistence()
    engine = DMXEngine(persistence=p)
    # start engine if not running
    engine.start()
    # only allow in SETUP
    state = p.get_setting('system.state', 'SETUP')
    if state != 'SETUP':
        raise HTTPException(status_code=409, detail='aim allowed only in SETUP')
    engine.aim_test(req.target_cm, req.duration_ms)
    return {"ok": True}


@router.post('/dmx/stop')
def stop():
    p = get_persistence()
    engine = DMXEngine(persistence=p)
    engine.stop_test()
    return {"ok": True}
# /dmx routes
