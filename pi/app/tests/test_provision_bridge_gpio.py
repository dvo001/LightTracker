from fastapi.testclient import TestClient

from app.main import app
from app.api import routes_devices
from app.bridge_client import BridgeError


class _DummyPersistence:
    def __init__(self, settings):
        self._settings = dict(settings)

    def get_setting(self, key, default=None):
        return self._settings.get(key, default)

    def upsert_device(self, _data):
        return None


def _base_settings():
    return {
        "wifi.ssid": "test-ssid",
        "wifi.pass": "test-pass",
        "mqtt.host": "127.0.0.1",
        "mqtt.port": "1883",
        "provision.token": "changeme",
        "provision.bridge_port": "/dev/serial0",
        "provision.bridge_baud": "115200",
    }


client = TestClient(app)


def test_provision_uses_pi_gpio_defaults(monkeypatch):
    p = _DummyPersistence(_base_settings())
    calls = []

    def _fake_call_bridge(port, baud, payload, timeout_s=8.0, **kwargs):
        calls.append(
            {
                "port": port,
                "baud": baud,
                "payload": payload,
                "timeout_s": timeout_s,
                "kwargs": kwargs,
            }
        )
        return {"status": "ok", "op": "provision_write_ack"}

    monkeypatch.setattr(routes_devices, "get_persistence", lambda: p)
    monkeypatch.setattr(routes_devices, "call_bridge", _fake_call_bridge)

    r = client.post("/api/v1/devices/AA:BB:CC:DD:EE:FF/provision", json={})
    assert r.status_code == 200
    assert len(calls) == 1
    assert calls[0]["port"] == "/dev/serial0"
    assert calls[0]["kwargs"]["reset_pin"] == 17
    assert calls[0]["kwargs"]["boot_pin"] == 27
    assert calls[0]["kwargs"]["auto_reset"] is True


def test_provision_fallback_without_gpio_backend(monkeypatch):
    p = _DummyPersistence(_base_settings())
    calls = []

    def _fake_call_bridge(port, baud, payload, timeout_s=8.0, **kwargs):
        calls.append({"timeout_s": timeout_s, "kwargs": kwargs})
        if kwargs.get("reset_pin") is not None:
            raise BridgeError("GPIO pins requested but no backend found. Install lgpio or RPi.GPIO.")
        return {"status": "ok", "op": "provision_write_ack"}

    monkeypatch.setattr(routes_devices, "get_persistence", lambda: p)
    monkeypatch.setattr(routes_devices, "call_bridge", _fake_call_bridge)

    r = client.post("/api/v1/devices/AA:BB:CC:DD:EE:11/provision", json={})
    assert r.status_code == 200
    assert len(calls) == 2
    assert calls[0]["kwargs"]["reset_pin"] == 17
    assert calls[0]["kwargs"]["boot_pin"] == 27
    assert calls[1]["kwargs"] == {}
