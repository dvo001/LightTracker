import time
import json
from typing import Dict, Any, Callable, Optional

from app.db.persistence import get_persistence
from .mapping import compute_pan_tilt, limit
from .frame_builder import build_frame, deg_to_u16
from .uart_rs485_driver import UartRs485Driver
from .artnet_driver import ArtnetDriver


class DmxEngine:
    def __init__(self, tracking_engine, driver: Optional[UartRs485Driver] = None, state_provider: Optional[Callable[[], str]] = None):
        self.tracking_engine = tracking_engine
        self.driver = driver
        self._driver_sig = None  # tracks driver mode/config to allow reload
        self._driver_managed = driver is None
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

        if self._driver_managed:
            self._ensure_driver(p)

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
                "universe": fx.get("universe", 0),
                "pan_u16": pan_u16,
                "tilt_u16": tilt_u16,
            })

        if commands and self.driver:
            frames = self._build_frames_by_universe(commands, profiles)
            for uni, frame in frames.items():
                try:
                    self.driver.send_frame(frame, universe=uni)
                except Exception as e:
                    p.append_event("ERROR", "dmx", "send_failed", ref=str(uni), details_json=str(e))

    def aim(self, target_cm: Dict[str, Any], duration_ms: int):
        self.test_target_cm = target_cm
        self.test_until_ms = int(time.time() * 1000) + duration_ms

    def stop_test(self):
        self.test_target_cm = None
        self.test_until_ms = None

    def send_custom_frame(self, universe: int, channel_values: Dict[int, int]):
        p = get_persistence()
        if self._driver_managed:
            self._ensure_driver(p)
        if not self.driver:
            return
        frame = bytearray(513)
        frame[0] = 0x00
        for ch, val in channel_values.items():
            if ch < 1 or ch > 512:
                continue
            frame[ch] = max(0, min(255, int(val)))
        try:
            self.driver.send_frame(bytes(frame), universe=universe)
        except Exception as e:
            p.append_event("ERROR", "dmx", "send_custom_failed", ref=str(universe), details_json=str(e))

    def _ensure_driver(self, persistence):
        def _as_int(val, default):
            try:
                return int(val)
            except Exception:
                return default

        mode = (persistence.get_setting("dmx.output_mode", "uart") or "uart").lower()
        if mode == "off":
            self.driver = None
            self._driver_sig = ("off",)
            return

        if mode == "artnet":
            target = persistence.get_setting("artnet.target_ip", "255.255.255.255") or "255.255.255.255"
            port = _as_int(persistence.get_setting("artnet.port", 6454), 6454)
            universe = _as_int(persistence.get_setting("artnet.universe", 0), 0)
            sig = ("artnet", target, port, universe)
            if sig != self._driver_sig:
                self.driver = ArtnetDriver(target_ip=target, port=port, default_universe=universe)
                self._driver_sig = sig
            return

        # default to UART RS485
        device = persistence.get_setting("dmx.uart_device", "/dev/serial0") or "/dev/serial0"
        sig = ("uart", device)
        if sig != self._driver_sig:
            self.driver = UartRs485Driver(device=device)
            self._driver_sig = sig

    def _build_frames_by_universe(self, commands, profiles):
        universes = {}
        grouped = {}
        for cmd in commands:
            uni = cmd.get("universe", 0) or 0
            grouped.setdefault(uni, []).append(cmd)
        for uni, cmds in grouped.items():
            frame = build_frame(cmds, profiles)
            if frame:
                universes[uni] = frame
        return universes
