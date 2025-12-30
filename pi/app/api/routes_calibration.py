from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.calibration_manager import CalibrationManager
from app.db.persistence import get_persistence
from app.core.state_manager import StateManager

router = APIRouter()
cm = CalibrationManager()
sm = StateManager()


class StartReq(BaseModel):
    tag_mac: str
    duration_ms: Optional[int] = 6000


@router.post('/calibration/start')
def start(req: StartReq):
    # only allowed in SETUP
    p = get_persistence()
    state = p.get_setting('system.state', 'SETUP')
    if state != 'SETUP':
        raise HTTPException(status_code=409, detail='STATE_BLOCKED')
    # check gates minimal
    gates = sm.gates()
    if gates['anchors_online'] < gates['anchors_required']:
        raise HTTPException(status_code=409, detail='NOT_READY')
    run_id = cm.start(req.tag_mac, req.duration_ms)
    return {'ok': True, 'run_id': run_id}


@router.post('/calibration/abort')
def abort():
    cm.abort()
    return {'ok': True}


@router.get('/calibration/runs')
def list_runs(tag_mac: Optional[str] = None):
    p = get_persistence()
    runs = p.list_calibration_runs(tag_mac)
    return {'runs': runs}


@router.get('/calibration/runs/{run_id}')
def get_run(run_id: int):
    p = get_persistence()
    r = p.get_calibration_run(run_id)
    if not r:
        raise HTTPException(status_code=404)
    return r
# /calibration routes
