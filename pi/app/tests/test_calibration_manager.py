import tempfile
import time
from app.core.calibration_manager import CalibrationManager
from app.db.persistence import get_persistence


def test_calibration_ok(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    monkeypatch.setenv('PI_DB_PATH', tmp.name)
    p = get_persistence()
    p.migrate()
    # seed anchor positions and rangecache
    from app.core.range_cache import get_range_cache
    rc = get_range_cache()
    tag = 'TAG1'
    # create 4 anchors with many samples
    anchors = ['A1','A2','A3','A4']
    for a in anchors:
        # put anchor positions
        conn = __import__('sqlite3').connect(tmp.name)
        conn.execute('INSERT OR REPLACE INTO anchor_positions(mac,x_cm,y_cm,z_cm,updated_at_ms) VALUES(?,?,?,?,?)',(a,0,0,0,int(time.time()*1000)))
        conn.commit()
        conn.close()
        # add samples
        batch = {'anchor_mac': a, 'ts_ms': int(time.time()*1000), 'ranges': [{'tag_mac': tag, 'd_m': 1.0}, {'tag_mac': tag, 'd_m': 1.01}, {'tag_mac': tag, 'd_m': 0.99}]}
        rc.update_from_batch(batch)

    cm = CalibrationManager()
    run_id = cm.start(tag, duration_ms=500)
    # wait until completion
    time.sleep(1.0)
    runs = p.list_calibration_runs(tag)
    assert len(runs) >= 1
    r = runs[0]
    assert r['result'] in ('OK','FAILED','ABORTED')

def test_abort(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    monkeypatch.setenv('PI_DB_PATH', tmp.name)
    p = get_persistence()
    p.migrate()
    from app.core.range_cache import get_range_cache
    rc = get_range_cache()
    tag = 'TAG_ABORT'
    cm = CalibrationManager()
    run_id = cm.start(tag, duration_ms=2000)
    time.sleep(0.1)
    cm.abort()
    time.sleep(0.1)
    r = p.get_calibration_run(run_id)
    assert r['result'] == 'ABORTED'
