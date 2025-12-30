import threading
import time
import json
import logging
from typing import Dict, Any

from app.db.persistence import get_persistence
from app.core.range_cache import get_range_cache
from app.core.trilateration import solve_3d

logger = logging.getLogger("pi.tracking")


class TrackingEngine:
    def __init__(self, persistence=None, mqtt_client=None):
        self.persistence = persistence or get_persistence()
        self.range_cache = get_range_cache()
        self.mqtt_client = mqtt_client
        self._stop = threading.Event()
        self._thread = None
        self.latest_position: Dict[str, Dict[str, Any]] = {}
        self._last_valid_ts: Dict[str, int] = {}

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self.run, daemon=True, name="tracking-engine")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def run(self):
        # determine tick rate
        try:
            rates_json = self.persistence.get_setting('rates.global')
            import json as _j
            rates = _j.loads(rates_json) if rates_json else {}
            hz = float(rates.get('tracking_hz', 10))
            stale_timeout_ms = int(rates.get('stale_timeout_ms', 5000))
            lost_timeout_ms = int(rates.get('lost_timeout_ms', 15000))
        except Exception:
            hz = 10.0
            stale_timeout_ms = 5000
            lost_timeout_ms = 15000

        period = 1.0 / hz if hz > 0 else 0.1
        logger.info("Tracking engine started at %.2f Hz", hz)

        while not self._stop.is_set():
            start = time.time()
            try:
                # list TAG devices from DB
                conn = __import__('sqlite3').connect(__import__('os').environ.get('PI_DB_PATH') or __import__('app').config.DB_PATH)
                cur = conn.execute("SELECT mac,role,status FROM devices WHERE role='TAG' AND status='ONLINE'")
                tags = [r[0] for r in cur.fetchall()]
                conn.close()
            except Exception:
                tags = []

            anchor_positions = self.persistence.get_anchor_positions()

            now_ms = int(time.time() * 1000)
            for tag in tags:
                samples = self.range_cache.snapshot(tag, max_age_ms=stale_timeout_ms)
                if not samples:
                    # no samples: maybe stale or lost
                    last_valid = self._last_valid_ts.get(tag)
                    age = now_ms - last_valid if last_valid else None
                    state = 'LOST' if (age and age > lost_timeout_ms) else 'STALE'
                    payload = {"tag_mac": tag, "ts_ms": now_ms, "state": state}
                    self.latest_position[tag] = payload
                    # publish
                    try:
                        if self.mqtt_client:
                            self.mqtt_client.publish(f"tracking/{tag}/position", json.dumps(payload))
                    except Exception:
                        logger.exception("Failed publish")
                    continue

                # attempt solve
                res = solve_3d(anchor_positions, samples)
                if res.pos_cm is None:
                    # solver failed
                    last_valid = self._last_valid_ts.get(tag)
                    age = now_ms - last_valid if last_valid else None
                    state = 'LOST' if (age and age > lost_timeout_ms) else 'STALE'
                    payload = {"tag_mac": tag, "ts_ms": now_ms, "state": state, "reason": res.reason}
                else:
                    x = res.pos_cm.tolist()
                    state = 'TRACKING'
                    payload = {"tag_mac": tag, "ts_ms": now_ms, "state": state, "x_cm": x[0], "y_cm": x[1], "z_cm": x[2], "anchors_used": res.anchors_used, "resid_m": res.resid_m}
                    self._last_valid_ts[tag] = now_ms

                self.latest_position[tag] = payload
                # publish
                try:
                    client = getattr(self.mqtt_client, 'client', self.mqtt_client)
                    if client:
                        # qos 0
                        client.publish(f"tracking/{tag}/position", json.dumps(payload))
                except Exception:
                    logger.exception("Failed publish")

            # sleep to maintain tick
            elapsed = time.time() - start
            to_sleep = period - elapsed
            if to_sleep > 0:
                time.sleep(to_sleep)
# Tracking engine
