import tempfile
from fastapi.testclient import TestClient


def test_invalidation(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    monkeypatch.setenv('PI_DB_PATH', tmp.name)
    from app.main import app
    client = TestClient(app)
    # create an OK calibration run manually
    from app.db.persistence import get_persistence
    p = get_persistence()
    p.migrate()
    run_id = p.create_calibration_run('TINV', '{}', 1)
    p.finish_calibration_run(run_id, 'OK', 2, '{}')
    # upsert anchor position -> should invalidate
    r = client.post('/api/v1/anchors/position', json={'mac': 'A1', 'x_cm': 0, 'y_cm': 0, 'z_cm': 0})
    assert r.status_code == 200
    runs = p.list_calibration_runs()
    # latest should have invalidated_at_ms set
    assert any(r.get('invalidated_at_ms') for r in runs if r.get('result') == 'OK')
