import os
import tempfile
from fastapi.testclient import TestClient

from app.main import app
from app.db.migrations.runner import run_migrations


def setup_module(_):
    # isolated DB
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    os.environ["LT_DB_PATH"] = tmp.name
    run_migrations(tmp.name)


client = TestClient(app)


def test_state_endpoint():
    r = client.get("/api/v1/state")
    assert r.status_code == 200
    assert "system_state" in r.json()


def test_settings_roundtrip():
    r = client.put("/api/v1/settings", json={"key": "foo", "value": "bar"})
    assert r.status_code == 200
    r2 = client.get("/api/v1/settings")
    assert r2.status_code == 200
    assert any(item["key"] == "foo" and item["value"] == "bar" for item in r2.json().get("settings", []))
