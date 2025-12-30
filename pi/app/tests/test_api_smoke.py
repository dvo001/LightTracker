import os
import tempfile

from fastapi.testclient import TestClient


def test_api_state_and_settings(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    db_path = tmp.name
    monkeypatch.setenv('PI_DB_PATH', db_path)

    # import app after setting env so migrations run on startup
    from app.main import app

    client = TestClient(app)

    r = client.get('/api/v1/state')
    assert r.status_code == 200
    assert 'system_state' in r.json()

    # settings roundtrip
    r = client.get('/api/v1/settings')
    assert r.status_code == 200
    r = client.put('/api/v1/settings', json={'key': 'test.k', 'value': '123'})
    assert r.status_code == 200
