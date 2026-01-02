import time
import json
from typing import Dict, Any, Callable, Optional

from app.db.persistence import get_persistence
from .mapping import compute_pan_tilt, limit
from .frame_builder import build_frame, deg_to_u16
from .uart_rs485_driver import UartRs485Driver


class DmxEngine:
    def __init__(self, tracking_engine, driver: Optional[UartRs485Driver] = None, state_provider: Optional[Callable[[], str]] = None):
        self.tracking_engine = tracking_engine
        self.driver = driver or UartRs485Driver()
        self.state_provider = state_provider or (lambda: get_persistence().get_setting("system.state", "SETUP"))
        self.last_sent: Dict[int, Dict[str, float]] = {}  # fixture_id -> {"pan_deg":..., "tilt_deg":...}
        self.test_target_cm = None
        self.test_until_ms = None

    def tick(self):
        p = get_persistence()
        fixtures = p.list_fixtures()
        profiles = {pr["profile_key"]: json.loads(pr["profile_json"]) if pr.get("profile_json") else {} for pr in p.list_fixture_profiles()}
        state = self.state_provider()
        now = int(time.time() * 1000)
        use_test = self.test_target_cm and self.test_until_ms and now < self.test_until_ms

        commands = []
        for fx in fixtures:
            if not fx.get("enabled", 1):
                continue
            target_pos = None
            if state == "LIVE" and not use_test:
                latest = self.tracking_engine.latest_position
                if latest:
                    # pick first tracked tag
                    pos = next(iter(latest.values()))
                    if pos.get("state") != "TRACKING":
                        continue
                    target_pos = pos.get("position_cm")
            if use_test:
                target_pos = self.test_target_cm
            if not target_pos:
                continue

            fixture_pos = {"x": fx.get("pos_x_cm", 0), "y": fx.get("pos_y_cm", 0), "z": fx.get("pos_z_cm", 0)}
            pan, tilt = compute_pan_tilt(fixture_pos, target_pos, fx)
            prev = self.last_sent.get(fx["id"], {"pan_deg": pan, "tilt_deg": tilt})
            dt_s = 0.033  # approx 30 Hz
            pan = limit(prev["pan_deg"], pan, fx.get("slew_pan_deg_s", 180), dt_s)
            tilt = limit(prev["tilt_deg"], tilt, fx.get("slew_tilt_deg_s", 180), dt_s)
            self.last_sent[fx["id"]] = {"pan_deg": pan, "tilt_deg": tilt}

            pan_u16 = deg_to_u16(pan, fx.get("pan_min_deg", 0), fx.get("pan_max_deg", 360))
            tilt_u16 = deg_to_u16(tilt, fx.get("tilt_min_deg", 0), fx.get("tilt_max_deg", 180))

            commands.append({
                "id": fx["id"],
                "profile_key": fx["profile_key"],
                "dmx_base_addr": fx["dmx_base_addr"],
                "pan_u16": pan_u16,
                "tilt_u16": tilt_u16,
            })

        if commands:
            frame = build_frame(commands, profiles)
            try:
                self.driver.send_frame(frame)
            except Exception as e:
                p.append_event("ERROR", "dmx", "send_failed", details_json=str(e))

    def aim(self, target_cm: Dict[str, Any], duration_ms: int):
        self.test_target_cm = target_cm
        self.test_until_ms = int(time.time() * 1000) + duration_ms

    def stop_test(self):
        self.test_target_cm = None
        self.test_until_ms = None
