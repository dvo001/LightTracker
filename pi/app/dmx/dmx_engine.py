import threading
import time
import json
import logging
from typing import Dict, Any

from app.db.persistence import get_persistence
from app.dmx import mapping, frame_builder, uart_rs485_driver

logger = logging.getLogger("pi.dmx")


class DMXEngine:
    def __init__(self, persistence=None):
        self.persistence = persistence or get_persistence()
        self.driver = uart_rs485_driver.UARTRS485Driver(device=self.persistence.get_setting('dmx.uart_device') or None)
        self._stop = threading.Event()
        self._thread = None
        self._last_frame = None
        self._last_positions: Dict[int, Dict[str, Any]] = {}
        self.test_mode = False
        self.test_target = None
        self.test_until = 0

    def start(self):
        self.driver.open()
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self.run, daemon=True, name="dmx-engine")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        self.driver.close()

    def run(self):
        try:
            rates_json = self.persistence.get_setting('rates.global')
            rates = json.loads(rates_json) if rates_json else {}
            hz = float(rates.get('dmx_hz', 30))
        except Exception:
            hz = 30.0
        period = 1.0 / hz if hz > 0 else 1.0/30.0
        logger.info("DMX engine starting at %.2f Hz", hz)

        # last commanded pan/tilt per fixture id
        last_cmds: Dict[int, Dict[str, float]] = {}

        while not self._stop.is_set():
            start = time.time()
            # read system state
            state = self.persistence.get_setting('system.state', 'SETUP')

            fixtures = self.persistence.list_fixtures()

            fixtures_commands = []
            now = int(time.time() * 1000)
            if self.test_mode and now < self.test_until and state == 'SETUP':
                # aim all fixtures to test_target
                target = self.test_target
                for f in fixtures:
                    if not f.get('is_enabled'):
                        continue
                    pan, tilt = mapping.compute_pan_tilt((f.get('pos_x_cm',0), f.get('pos_y_cm',0), f.get('pos_z_cm',0)), (target[0], target[1], target[2]))
                    pan, tilt = mapping.apply_limits_and_offsets(pan, tilt, f)
                    prev = last_cmds.get(f['id'], {'pan': pan, 'tilt': tilt})
                    dt = period
                    pan_l = mapping.limit(prev['pan'], pan, f.get('slew_pan_deg_s', 180.0), dt)
                    tilt_l = mapping.limit(prev['tilt'], tilt, f.get('slew_tilt_deg_s', 180.0), dt)
                    last_cmds[f['id']] = {'pan': pan_l, 'tilt': tilt_l}
                    pan_u = frame_builder.deg_to_u16(pan_l, f.get('pan_min_deg', -180), f.get('pan_max_deg',180))
                    tilt_u = frame_builder.deg_to_u16(tilt_l, f.get('tilt_min_deg', -90), f.get('tilt_max_deg',90))
                    fixtures_commands.append({'dmx_base_addr': f.get('dmx_base_addr'), 'pan_u16': pan_u, 'tilt_u16': tilt_u, 'id': f['id']})
            elif state == 'LIVE':
                # get positions from tracking engine
                try:
                    import app
                    tracking = getattr(app.main.app.state, 'tracking_engine', None)
                    if tracking:
                        for f in fixtures:
                            if not f.get('is_enabled'):
                                continue
                            # choose target: tag position nearest or skip; v1: aim at first TRACKING tag
                            target_pos = None
                            for tag, payload in tracking.latest_position.items():
                                if payload.get('state') == 'TRACKING':
                                    target_pos = (payload.get('x_cm'), payload.get('y_cm'), payload.get('z_cm'))
                                    break
                            if not target_pos:
                                # freeze
                                continue
                            pan, tilt = mapping.compute_pan_tilt((f.get('pos_x_cm',0), f.get('pos_y_cm',0), f.get('pos_z_cm',0)), target_pos)
                            pan, tilt = mapping.apply_limits_and_offsets(pan, tilt, f)
                            prev = last_cmds.get(f['id'], {'pan': pan, 'tilt': tilt})
                            dt = period
                            pan_l = mapping.limit(prev['pan'], pan, f.get('slew_pan_deg_s', 180.0), dt)
                            tilt_l = mapping.limit(prev['tilt'], tilt, f.get('slew_tilt_deg_s', 180.0), dt)
                            last_cmds[f['id']] = {'pan': pan_l, 'tilt': tilt_l}
                            pan_u = frame_builder.deg_to_u16(pan_l, f.get('pan_min_deg', -180), f.get('pan_max_deg',180))
                            tilt_u = frame_builder.deg_to_u16(tilt_l, f.get('tilt_min_deg', -90), f.get('tilt_max_deg',90))
                            fixtures_commands.append({'dmx_base_addr': f.get('dmx_base_addr'), 'pan_u16': pan_u, 'tilt_u16': tilt_u, 'id': f['id']})
                except Exception:
                    logger.exception("Error fetching tracking positions")
            else:
                # non-LIVE: freeze -> reuse last frame
                fixtures_commands = []

            # build frame
            frame = frame_builder.build_frame(fixtures_commands, None)
            success = self.driver.send_frame(frame)
            if not success:
                logger.error("DMX send_frame failed")
                # escalate to SAFE
                self.persistence.insert_event('ERROR', 'dmx', 'send_failed', '', 'send_frame failed')
                # try to set system.state = SAFE
                try:
                    import sqlite3, os
                    db = os.environ.get('PI_DB_PATH') or __import__('app').config.DB_PATH
                    conn = sqlite3.connect(db)
                    ts = int(time.time() * 1000)
                    conn.execute("INSERT OR REPLACE INTO settings(key,value,updated_at_ms) VALUES(?,?,?)", ('system.state','SAFE',ts))
                    conn.commit()
                    conn.close()
                except Exception:
                    logger.exception("Failed to set SAFE state")

            self._last_frame = frame
            elapsed = time.time() - start
            to_sleep = period - elapsed
            if to_sleep > 0:
                time.sleep(to_sleep)

    # test control
    def aim_test(self, target_cm, duration_ms):
        self.test_mode = True
        self.test_target = target_cm
        self.test_until = int(time.time() * 1000) + int(duration_ms)

    def stop_test(self):
        self.test_mode = False
        self.test_target = None
        self.test_until = 0
# DMX engine
