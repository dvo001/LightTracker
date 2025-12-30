import time
from typing import Dict, Any

from app.db.persistence import get_persistence


class StateManager:
    def __init__(self, persistence=None):
        self.persistence = persistence or get_persistence()

    def gates(self) -> Dict[str, Any]:
        p = self.persistence
        # mqtt_ok: best-effort - for now always True if setting exists
        mqtt_ok = True
        # anchors online count
        try:
            conn = __import__('sqlite3').connect(__import__('os').environ.get('PI_DB_PATH') or __import__('app').config.DB_PATH)
            cur = conn.execute("SELECT COUNT(*) FROM anchor_positions WHERE x_cm IS NOT NULL")
            anchors_with_pos = cur.fetchone()[0]
            conn.close()
        except Exception:
            anchors_with_pos = 0

        settings = p.get_setting('rates.global')
        guards_min = int(p.get_setting('guards.min_anchors_online') or 4)

        # latest valid calibration exists
        runs = p.list_calibration_runs()
        calibration_ok = False
        for r in runs:
            if r.get('result') == 'OK' and not r.get('invalidated_at_ms'):
                calibration_ok = True
                break

        fixtures_ok = len(p.list_fixtures()) > 0

        dmx_ok = True

        tags_online = 0
        try:
            conn = __import__('sqlite3').connect(__import__('os').environ.get('PI_DB_PATH') or __import__('app').config.DB_PATH)
            cur = conn.execute("SELECT COUNT(*) FROM devices WHERE role='TAG' AND status='ONLINE'")
            tags_online = cur.fetchone()[0]
            conn.close()
        except Exception:
            tags_online = 0

        return {
            'mqtt_ok': mqtt_ok,
            'anchors_online': anchors_with_pos,
            'anchors_required': guards_min,
            'calibration_ok': calibration_ok,
            'fixtures_ok': fixtures_ok,
            'dmx_ok': dmx_ok,
            'tags_online': tags_online,
        }

    def can_enter_live(self) -> bool:
        g = self.gates()
        return g['mqtt_ok'] and g['anchors_online'] >= g['anchors_required'] and g['calibration_ok'] and g['fixtures_ok'] and g['tags_online'] >= 1
# Operational state manager
