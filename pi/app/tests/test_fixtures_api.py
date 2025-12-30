import tempfile
from fastapi.testclient import TestClient


def test_fixtures_crud(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    monkeypatch.setenv('PI_DB_PATH', tmp.name)
    # ensure migrations run
    from app.main import app
    client = TestClient(app)
    # list profiles (seed exists)
    r = client.get('/api/v1/fixture-profiles')
    assert r.status_code == 200
    # create fixture
    payload = {"name": "f1", "dmx_base_addr": 1, "profile_key": "generic_mh_16bit_v1"}
    r = client.post('/api/v1/fixtures', json=payload)
    assert r.status_code == 200
    fid = r.json().get('id')
    assert fid
    r = client.get(f'/api/v1/fixtures/{fid}')
    assert r.status_code == 200
    # update
    r = client.put(f'/api/v1/fixtures/{fid}', json={'name': 'updated'})
    assert r.status_code == 200
    # delete
    r = client.delete(f'/api/v1/fixtures/{fid}')
    assert r.status_code == 200
