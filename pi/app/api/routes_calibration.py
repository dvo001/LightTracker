from fastapi import APIRouter, HTTPException, Request
from ..db import connect_db
import time
import asyncio
import json

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


@router.get('/calibration/status')
def calibration_status(request: Request):
    st = request.app.state
    active = getattr(st, 'active_calibration', None)
    if not active:
        return {'running': False, 'run_id': None, 'tag_mac': None, 'started_at_ms': None, 'progress': {}}
    # return snapshot
    return {
        'running': True,
        'run_id': active.get('run_id'),
        'tag_mac': active.get('tag_mac'),
        'started_at_ms': active.get('started_at_ms'),
        'progress': active.get('progress', {})
    }


@router.post('/calibration/start')
async def calibration_start(payload: dict, request: Request):
    tag_mac = payload.get('tag_mac')
    duration_ms = int(payload.get('duration_ms', 6000))
    if not tag_mac:
        raise HTTPException(status_code=400, detail='tag_mac required')

    db = connect_db()
    try:
        ensure_calibration_table(db)
        ts = int(time.time() * 1000)
        cur = db.execute('INSERT INTO calibration_runs (tag_mac, started_at_ms, status, params_json) VALUES (?,?,?,?)', (
            tag_mac, ts, 'running', json.dumps({'duration_ms': duration_ms})
        ))
        db.commit()
        run_id = cur.lastrowid
    finally:
        db.close()

    # store active run in app state
    st = request.app.state
    st.active_calibration = {
        'run_id': run_id,
        'tag_mac': tag_mac,
        'started_at_ms': ts,
        'duration_ms': duration_ms,
        'progress': {'samples': 0, 'duration_ms': 0}
    }

    # start background task to simulate collection
    loop = asyncio.get_event_loop()
    loop.create_task(_run_calibration_simulator(request.app, run_id))

    return {'ok': True, 'run_id': run_id}


async def _run_calibration_simulator(app, run_id: int):
    st = app.state
    active = getattr(st, 'active_calibration', None)
    if not active or active.get('run_id') != run_id:
        return
    duration = active.get('duration_ms', 6000)
    start = active.get('started_at_ms')
    interval = 0.5
    elapsed = 0.0
    samples = 0
    while elapsed * 1000 < duration:
        await asyncio.sleep(interval)
        elapsed += interval
        samples += 1
        active['progress'] = {'samples': samples, 'duration_ms': int(elapsed*1000)}
    # finish run
    ts_end = int(time.time() * 1000)
    # write result
    db = connect_db()
    try:
        summary = {'samples': samples, 'duration_ms': int(elapsed*1000), 'result': 'OK'}
        db.execute('UPDATE calibration_runs SET ended_at_ms=?, result=?, summary_json=?, status=? WHERE id=?', (
            ts_end, 'OK', json.dumps(summary), 'finished', run_id
        ))
        db.commit()
    finally:
        db.close()
    # clear active
    st.active_calibration = None


@router.post('/calibration/abort')
def calibration_abort(request: Request):
    st = request.app.state
    active = getattr(st, 'active_calibration', None)
    if not active:
        return {'ok': False, 'error': 'no active run'}
    run_id = active.get('run_id')
    ts = int(time.time() * 1000)
    db = connect_db()
    try:
        db.execute('UPDATE calibration_runs SET ended_at_ms=?, result=?, status=? WHERE id=?', (ts, 'ABORTED', 'aborted', run_id))
        db.commit()
    finally:
        db.close()
    st.active_calibration = None
    return {'ok': True, 'run_id': run_id}


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
