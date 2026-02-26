from fastapi.testclient import TestClient

from app.main import app
from app.api import routes_dmx
from app.dmx.dmx_engine import DmxEngine
from app.dmx.bridge_uart_driver import BridgeUartDmxDriver


class _DummyPersistence:
    def __init__(self, settings=None):
        self._settings = dict(settings or {})

    def get_setting(self, key, default=None):
        return self._settings.get(key, default)

    def upsert_setting(self, key, value):
        self._settings[key] = str(value)


client = TestClient(app)


def test_put_dmx_config_bridge_mode(monkeypatch):
    p = _DummyPersistence({"system.state": "SETUP"})
    monkeypatch.setattr(routes_dmx, "get_persistence", lambda: p)

    r = client.put(
        "/api/v1/dmx/config",
        json={
            "mode": "bridge",
            "bridge_port": "/dev/ttyUSB0",
            "bridge_baud": 921600,
        },
    )
    assert r.status_code == 200
    cfg = r.json().get("config", {})
    assert cfg.get("mode") == "bridge"
    assert cfg.get("bridge_port") == "/dev/ttyUSB0"
    assert int(cfg.get("bridge_baud")) == 921600
    assert p.get_setting("dmx.output_mode") == "bridge"
    assert p.get_setting("dmx.bridge_port") == "/dev/ttyUSB0"
    assert p.get_setting("dmx.bridge_baud") == "921600"


def test_put_dmx_config_rejects_unknown_mode(monkeypatch):
    p = _DummyPersistence({"system.state": "SETUP"})
    monkeypatch.setattr(routes_dmx, "get_persistence", lambda: p)

    r = client.put("/api/v1/dmx/config", json={"mode": "foobar"})
    assert r.status_code == 400


def test_dmx_engine_selects_bridge_driver():
    class _TE:
        latest_position = {}

    p = _DummyPersistence(
        {
            "dmx.output_mode": "bridge",
            "dmx.bridge_port": "/dev/ttyUSB9",
            "dmx.bridge_baud": "115200",
        }
    )
    eng = DmxEngine(tracking_engine=_TE(), state_provider=lambda: "SETUP")
    eng._ensure_driver(p)
    assert isinstance(eng.driver, BridgeUartDmxDriver)
