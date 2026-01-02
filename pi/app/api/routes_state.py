from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..db import connect_db
from app.db.persistence import get_persistence
from app.core.state_manager import StateManager
import time

router = APIRouter()


class StateUpdate(BaseModel):
    state: str


@router.get('/state')
def get_state():
    p = get_persistence()
    sm = StateManager()
    system_state = sm.get_state()
    db = connect_db()
    try:
        cur = db.execute('SELECT COUNT(1) as cnt FROM fixtures')
        fixtures_cnt = cur.fetchone()['cnt'] if cur else 0
    except Exception:
        fixtures_cnt = 0
    finally:
        db.close()

    readiness = sm.readiness()
    return {
        'system_state': system_state,
        'mqtt_ok': readiness.get('mqtt_ok'),
        'anchors_online': readiness.get('anchors_online'),
        'fixtures_count': fixtures_cnt,
        'ts_ms': int(time.time() * 1000)
    }


@router.post('/state')
def set_state(body: StateUpdate):
    desired = body.state.upper()
    sm = StateManager()
    current = sm.get_state()
    if desired == current:
        return {'ok': True, 'system_state': desired}
    if desired == 'LIVE':
        ready = sm.readiness()
        if not ready.get('ready'):
            raise HTTPException(status_code=409, detail={'code': 'STATE_BLOCKED', 'message': 'Prerequisites not met', 'readiness': ready})
    if desired not in ('SETUP', 'SAFE', 'LIVE'):
        raise HTTPException(status_code=409, detail={'code': 'STATE_BLOCKED', 'message': 'Invalid state'})
    sm.set_state(desired)
    return {'ok': True, 'system_state': desired}
