import time
import json
from typing import Dict, Any, Callable, Optional

from app.db.persistence import get_persistence
from .mapping import compute_pan_tilt, limit
from .frame_builder import build_frame, deg_to_u16, u16_to_coarse_fine
from .uart_rs485_driver import UartRs485Driver
from .artnet_driver import ArtnetDriver


class DmxEngine:
    def __init__(self, tracking_engine, driver: Optional[UartRs485Driver] = None, state_provider: Optional[Callable[[], str]] = None):
        self.tracking_engine = tracking_engine
        self.driver = driver
        self._driver_sig = None  # tracks driver mode/config to allow reload
        self._driver_managed = driver is None
        self.state_provider = state_provider or (lambda: get_persistence().get_setting("system.state", "SETUP"))
        self.last_sent: Dict[Any, Dict[str, float]] = {}  # fixture_id or ofl:patch_id -> {"pan_deg":..., "tilt_deg":...}
        self.test_target_cm = None
        self.test_until_ms = None
        self._ofl_fixture_cache: Dict[int, Dict[str, Any]] = {}
        self._ofl_channel_cache: Dict[tuple, Dict[str, Optional[int]]] = {}
        self._ofl_color_cache: Dict[tuple, Dict[str, Optional[int]]] = {}
        self._color_overrides: Dict[int, Dict[str, int]] = {}

    def tick(self):
        p = get_persistence()
        fixtures = p.list_fixtures()
        patched = p.list_patched_fixtures()
        profiles = {pr["profile_key"]: json.loads(pr["profile_json"]) if pr.get("profile_json") else {} for pr in p.list_fixture_profiles()}
        state = self.state_provider()
        now = int(time.time() * 1000)
        use_test = self.test_target_cm and self.test_until_ms and now < self.test_until_ms

        if self._driver_managed:
            self._ensure_driver(p)

        target_pos = None
        if state == "LIVE" and not use_test:
            pos = self._select_tracking_payload(p)
            if pos:
                target_pos = pos.get("position_cm")
        if use_test:
            target_pos = self.test_target_cm

        commands = []
        for fx in fixtures:
            if not fx.get("enabled", 1):
                continue
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

        for patch in patched:
            if not target_pos:
                continue
            fixture_obj = self._load_ofl_fixture(p, patch.get("fixture_id"))
            if not fixture_obj:
                continue
            chan_map = self._ofl_get_pan_tilt_channels(patch.get("fixture_id"), patch.get("mode_name"), fixture_obj)
            if not chan_map or (chan_map.get("pan") is None and chan_map.get("tilt") is None):
                continue
            overrides = self._parse_overrides(patch.get("overrides_json"))
            fixture_pos = {
                "x": overrides.get("pos_x_cm", 0),
                "y": overrides.get("pos_y_cm", 0),
                "z": overrides.get("pos_z_cm", 0),
            }
            cfg = {
                "invert_pan": bool(overrides.get("invert_pan", 0)),
                "invert_tilt": bool(overrides.get("invert_tilt", 0)),
            }
            pan, tilt = compute_pan_tilt(fixture_pos, target_pos, cfg)
            key = f"ofl:{patch.get('id')}"
            prev = self.last_sent.get(key, {"pan_deg": pan, "tilt_deg": tilt})
            dt_s = 0.033
            pan = limit(prev["pan_deg"], pan, overrides.get("slew_pan_deg_s", 180), dt_s)
            tilt = limit(prev["tilt_deg"], tilt, overrides.get("slew_tilt_deg_s", 180), dt_s)
            self.last_sent[key] = {"pan_deg": pan, "tilt_deg": tilt}

            pan_u16 = deg_to_u16(pan, overrides.get("pan_min_deg", -360), overrides.get("pan_max_deg", 360))
            tilt_u16 = deg_to_u16(tilt, overrides.get("tilt_min_deg", -180), overrides.get("tilt_max_deg", 180))
            base_addr = patch.get("dmx_address", 1)
            channel_values = self._ofl_build_channel_values(base_addr, pan_u16, tilt_u16, chan_map)
            if not channel_values:
                continue
            color = self._color_overrides.get(patch.get("id"))
            if color:
                color_map = self._ofl_get_color_channels(patch.get("fixture_id"), patch.get("mode_name"), fixture_obj)
                color_values = self._ofl_build_color_values(base_addr, color, color_map)
                if color_values:
                    channel_values.update(color_values)
            commands.append({
                "id": key,
                "universe": patch.get("universe", 0),
                "channel_values": channel_values,
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

    def set_live_color(self, patch_id: int, r: int, g: int, b: int, dim: int):
        self._color_overrides[int(patch_id)] = {
            "r": int(max(0, min(255, r))),
            "g": int(max(0, min(255, g))),
            "b": int(max(0, min(255, b))),
            "dim": int(max(0, min(255, dim))),
        }

    def clear_live_color(self, patch_id: int):
        self._color_overrides.pop(int(patch_id), None)

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

    def _parse_overrides(self, raw):
        if not raw:
            return {}
        if isinstance(raw, dict):
            return raw
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _select_tracking_payload(self, persistence):
        latest = getattr(self.tracking_engine, "latest_position", {}) or {}
        if not latest:
            return None

        preferred = (persistence.get_setting("tracking.tag_mac", "") or "").strip()
        if preferred:
            payload = latest.get(preferred)
            if payload and payload.get("state") == "TRACKING":
                return payload

        best = None
        for payload in latest.values():
            if payload.get("state") != "TRACKING":
                continue
            if not best or (payload.get("ts_ms", 0) > best.get("ts_ms", 0)):
                best = payload
        return best

    def _load_ofl_fixture(self, persistence, fixture_id: Optional[int]):
        if not fixture_id:
            return None
        if fixture_id in self._ofl_fixture_cache:
            return self._ofl_fixture_cache[fixture_id]
        row = persistence.get_ofl_fixture(fixture_id)
        if not row:
            return None
        try:
            obj = json.loads(row.get("ofl_json") or "{}")
        except Exception:
            obj = {}
        self._ofl_fixture_cache[fixture_id] = obj
        return obj

    def _ofl_get_pan_tilt_channels(self, fixture_id: int, mode_name: str, fixture_obj: dict):
        key = (fixture_id, mode_name)
        if key in self._ofl_channel_cache:
            return self._ofl_channel_cache[key]
        modes = fixture_obj.get("modes") or []
        target_mode = None
        for m in modes:
            if isinstance(m, dict) and (m.get("name") or m.get("modeName")) == mode_name:
                target_mode = m
                break
        if not target_mode:
            return None
        chan_list = target_mode.get("channels") or []
        available = fixture_obj.get("availableChannels") or {}

        def classify(label: str):
            lower = (label or "").lower()
            if not lower:
                return None
            if "speed" in lower or "time" in lower or "macro" in lower or "accel" in lower:
                return None
            is_pan = "pan" in lower
            is_tilt = "tilt" in lower
            if not (is_pan or is_tilt):
                return None
            is_fine = "fine" in lower or "lsb" in lower or "16" in lower
            return is_pan, is_tilt, is_fine

        pan_idx = None
        pan_fine_idx = None
        tilt_idx = None
        tilt_fine_idx = None
        for idx, ch in enumerate(chan_list, start=0):
            key_name = ch if isinstance(ch, str) else ch.get("name") if isinstance(ch, dict) else None
            details = available.get(key_name) if isinstance(available, dict) else {}
            label = ""
            if isinstance(details, dict):
                label = details.get("name") or ""
            label = label or (key_name or "")

            res = classify(label) or classify(key_name or "")
            if not res and isinstance(details, dict):
                caps = details.get("capabilities") or []
                for cap in caps:
                    typ = (cap.get("type") or "")
                    res = classify(typ)
                    if res:
                        break
            if not res:
                continue
            is_pan, is_tilt, is_fine = res
            if is_pan:
                if is_fine:
                    pan_fine_idx = idx
                elif pan_idx is None:
                    pan_idx = idx
            if is_tilt:
                if is_fine:
                    tilt_fine_idx = idx
                elif tilt_idx is None:
                    tilt_idx = idx

        if pan_idx is None and pan_fine_idx is not None:
            pan_idx = pan_fine_idx
            pan_fine_idx = None
        if tilt_idx is None and tilt_fine_idx is not None:
            tilt_idx = tilt_fine_idx
            tilt_fine_idx = None

        out = {"pan": pan_idx, "pan_fine": pan_fine_idx, "tilt": tilt_idx, "tilt_fine": tilt_fine_idx}
        self._ofl_channel_cache[key] = out
        return out

    def _ofl_get_color_channels(self, fixture_id: int, mode_name: str, fixture_obj: dict):
        key = (fixture_id, mode_name, "color")
        if key in self._ofl_color_cache:
            return self._ofl_color_cache[key]
        modes = fixture_obj.get("modes") or []
        target_mode = None
        for m in modes:
            if isinstance(m, dict) and (m.get("name") or m.get("modeName")) == mode_name:
                target_mode = m
                break
        if not target_mode:
            return None
        chan_list = target_mode.get("channels") or []
        available = fixture_obj.get("availableChannels") or {}

        def label_for(ch):
            key_name = ch if isinstance(ch, str) else ch.get("name") if isinstance(ch, dict) else None
            details = available.get(key_name) if isinstance(available, dict) else {}
            label = ""
            if isinstance(details, dict):
                label = details.get("name") or ""
            return (label or key_name or "").strip(), details

        def classify(label: str):
            lower = (label or "").lower()
            if not lower:
                return None, False
            is_fine = "fine" in lower or "lsb" in lower or "16" in lower
            if "red" in lower:
                return "red", is_fine
            if "green" in lower:
                return "green", is_fine
            if "blue" in lower:
                return "blue", is_fine
            if "white" in lower:
                return "white", is_fine
            if "dim" in lower or "intensity" in lower:
                return "dimmer", is_fine
            if "shutter" in lower or "strobe" in lower:
                return "shutter", is_fine
            return None, is_fine

        def pick(existing, idx, is_fine, allow_fine=False):
            if existing is not None:
                return existing
            if is_fine and not allow_fine:
                return existing
            return idx

        r = {"coarse": None, "fine": None}
        g = {"coarse": None, "fine": None}
        b = {"coarse": None, "fine": None}
        w = {"coarse": None, "fine": None}
        dim = {"coarse": None, "fine": None}
        sh = {"coarse": None, "fine": None}

        for idx, ch in enumerate(chan_list, start=0):
            label, details = label_for(ch)
            kind, is_fine = classify(label)
            if not kind and isinstance(details, dict):
                for cap in (details.get("capabilities") or []):
                    typ = (cap.get("type") or "")
                    kind, is_fine = classify(typ)
                    if kind:
                        break
            if not kind:
                continue
            bucket = {"red": r, "green": g, "blue": b, "white": w, "dimmer": dim, "shutter": sh}.get(kind)
            if bucket is None:
                continue
            if is_fine:
                if bucket["fine"] is None:
                    bucket["fine"] = idx
            else:
                if bucket["coarse"] is None:
                    bucket["coarse"] = idx

        out = {
            "red": r["coarse"] if r["coarse"] is not None else r["fine"],
            "green": g["coarse"] if g["coarse"] is not None else g["fine"],
            "blue": b["coarse"] if b["coarse"] is not None else b["fine"],
            "white": w["coarse"] if w["coarse"] is not None else w["fine"],
            "dimmer": dim["coarse"] if dim["coarse"] is not None else dim["fine"],
            "shutter": sh["coarse"] if sh["coarse"] is not None else sh["fine"],
        }
        self._ofl_color_cache[key] = out
        return out

    def _ofl_build_channel_values(self, base_addr: int, pan_u16: int, tilt_u16: int, chan_map: dict):
        if not chan_map:
            return {}
        base = int(base_addr or 1)
        pan_coarse, pan_fine = u16_to_coarse_fine(pan_u16)
        tilt_coarse, tilt_fine = u16_to_coarse_fine(tilt_u16)
        values = {}

        def set_ch(idx, val):
            if idx is None:
                return
            ch = base + idx
            if ch < 1 or ch > 512:
                return
            values[ch] = val

        set_ch(chan_map.get("pan"), pan_coarse)
        set_ch(chan_map.get("pan_fine"), pan_fine)
        set_ch(chan_map.get("tilt"), tilt_coarse)
        set_ch(chan_map.get("tilt_fine"), tilt_fine)
        return values

    def _ofl_build_color_values(self, base_addr: int, color: dict, chan_map: dict):
        if not chan_map or not color:
            return {}
        base = int(base_addr or 1)
        values = {}

        def set_ch(idx, val):
            if idx is None:
                return
            ch = base + idx
            if ch < 1 or ch > 512:
                return
            values[ch] = val

        dim = int(max(0, min(255, color.get("dim", 255))))
        r = int(max(0, min(255, color.get("r", 0))))
        g = int(max(0, min(255, color.get("g", 0))))
        b = int(max(0, min(255, color.get("b", 0))))

        if chan_map.get("dimmer") is None:
            scale = dim / 255.0 if dim < 255 else 1.0
            r = int(r * scale)
            g = int(g * scale)
            b = int(b * scale)
        else:
            set_ch(chan_map.get("dimmer"), dim)

        if chan_map.get("shutter") is not None:
            set_ch(chan_map.get("shutter"), 255 if dim > 0 else 0)

        set_ch(chan_map.get("red"), r)
        set_ch(chan_map.get("green"), g)
        set_ch(chan_map.get("blue"), b)
        if chan_map.get("white") is not None:
            set_ch(chan_map.get("white"), dim)
        return values
