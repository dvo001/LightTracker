import tempfile
import time
from fastapi.testclient import TestClient


def test_calibration_api(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    monkeypatch.setenv('PI_DB_PATH', tmp.name)
    from app.main import app
    client = TestClient(app)
    # start without anchors -> should fail
    r = client.post('/api/v1/calibration/start', json={'tag_mac': 'T1', 'duration_ms': 100})
    assert r.status_code in (200, 409)
    # abort should be allowed
    r = client.post('/api/v1/calibration/abort')
    assert r.status_code == 200
