from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from ..db import connect_db
import time
import asyncio
import json

from app.core.calibration_manager import CalibrationManager
from app.core.state_manager import StateManager

router = APIRouter()


def ensure_calibration_table(db):
    db.execute('''CREATE TABLE IF NOT EXISTS calibration_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tag_mac TEXT,
        started_at_ms INTEGER,
        ended_at_ms INTEGER,
        result TEXT,
        invalidated_at_ms INTEGER,
        params_json TEXT,
        summary_json TEXT,
        status TEXT,
        committed_at_ms INTEGER,
        discarded_at_ms INTEGER
    )''')
    db.commit()


class CalStart(BaseModel):
    tag_mac: str
    duration_ms: int = Field(6000, ge=100, le=60000)


@router.get('/calibration/status')
def calibration_status(request: Request):
    cm = getattr(request.app.state, 'calibration_manager', None)
    if not cm:
        return {'running': False, 'run_id': None, 'tag_mac': None, 'started_at_ms': None, 'progress': {}}
    return cm.status()


@router.post('/calibration/start')
async def calibration_start(payload: CalStart, request: Request):
    sm = StateManager()
    if sm.get_state() == "LIVE":
        raise HTTPException(status_code=409, detail={'code': 'STATE_BLOCKED', 'message': 'Cannot start calibration while LIVE'})
    cm = getattr(request.app.state, 'calibration_manager', None)
    if not cm:
        # init on demand
        from app.core.tracking_engine import TrackingEngine
        te = getattr(request.app.state, 'tracking_engine', TrackingEngine())
        cm = CalibrationManager(te.range_cache)
        request.app.state.calibration_manager = cm
    try:
        run_id = cm.start(payload.tag_mac, payload.duration_ms)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    # schedule ticking loop
    loop = asyncio.get_event_loop()
    loop.create_task(_cal_tick_loop(cm))
    sm.set_state("CALIBRATION")
    return {'ok': True, 'run_id': run_id}


async def _cal_tick_loop(cm: CalibrationManager):
    while cm.active:
        cm.tick()
        await asyncio.sleep(0.1)
    # done -> set state back to SETUP
    sm = StateManager()
    sm.set_state("SETUP")


@router.post('/calibration/abort')
def calibration_abort(request: Request):
    cm = getattr(request.app.state, 'calibration_manager', None)
    if not cm or not cm.active:
        return {'ok': False, 'error': 'no active run'}
    cm.abort()
    StateManager().set_state("SETUP")
    return {'ok': True, 'run_id': None}


@router.post('/calibration/commit/{run_id}')
def calibration_commit(run_id: int):
    db = connect_db()
    try:
        db.execute('UPDATE calibration_runs SET status=?, committed_at_ms=? WHERE id=?', ('committed', int(time.time()*1000), run_id))
        db.commit()
    finally:
        db.close()
    return {'ok': True, 'run_id': run_id}


@router.post('/calibration/discard/{run_id}')
def calibration_discard(run_id: int):
    db = connect_db()
    try:
        db.execute('UPDATE calibration_runs SET status=?, discarded_at_ms=? WHERE id=?', ('discarded', int(time.time()*1000), run_id))
        db.commit()
    finally:
        db.close()
    return {'ok': True, 'run_id': run_id}


@router.get('/calibration/runs')
def list_runs():
    db = connect_db()
    try:
        ensure_calibration_table(db)
        rows = db.execute('SELECT * FROM calibration_runs ORDER BY id DESC LIMIT 200').fetchall()
        runs = [dict(r) for r in rows]
    finally:
        db.close()
    return {'runs': runs}


@router.get('/calibration/runs/{run_id}')
def get_run(run_id: int):
    db = connect_db()
    try:
        ensure_calibration_table(db)
        row = db.execute('SELECT * FROM calibration_runs WHERE id=?', (run_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='not found')
        r = dict(row)
    finally:
        db.close()
    return r
