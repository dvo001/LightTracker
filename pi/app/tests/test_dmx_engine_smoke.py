from app.dmx.dmx_engine import DmxEngine
from app.dmx.uart_rs485_driver import UartRs485Driver
from app.db.persistence import get_persistence


class DummyDriver(UartRs485Driver):
    def __init__(self):
        self.sent = []

    def send_frame(self, frame: bytes):
        self.sent.append(frame)


def test_dmx_engine_smoke(monkeypatch):
    drv = DummyDriver()
    class TE:
        latest_position = {"T1": {"state": "TRACKING", "position_cm": {"x": 50, "y": 50, "z": 50}}}
    te = TE()
    eng = DmxEngine(tracking_engine=te, driver=drv, state_provider=lambda: "LIVE")
    p = get_persistence()
    # ensure fixture profile exists
    if not p.list_fixture_profiles():
        p.upsert_setting("dummy", "1")  # just to touch db
    # create fixture
    fid = p.create_fixture({"name": "fx", "profile_key": "generic_mh_16bit_v1", "universe": 1, "dmx_base_addr": 1, "pos_x_cm": 0, "pos_y_cm": 0, "pos_z_cm": 0})
    eng.tick()
    assert drv.sent, "DMX frame should be sent"
