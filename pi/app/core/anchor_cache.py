import time
from typing import Dict, Tuple
from ..db import connect_db
from .anchor_positions import load_anchor_offsets

class AnchorCache:
    def __init__(self, refresh_ms:int=1000, online_window_ms:int=8000):
        self.refresh_ms = refresh_ms
        self.online_window_ms = online_window_ms
        self._cache = None
        self._ts = 0

    def _read_db(self):
        db = connect_db()
        try:
            rows = db.execute('SELECT mac,x_cm,y_cm,z_cm,updated_at_ms FROM anchor_positions').fetchall()
            offsets = load_anchor_offsets(db)
            anchors = {}
            for r in rows:
                dx, dy, dz = offsets.get(r["mac"], (0.0, 0.0, 0.0))
                anchors[r['mac']] = (r['x_cm'] + dx, r['y_cm'] + dy, r['z_cm'] + dz)
            devs = db.execute('SELECT mac, last_seen_at_ms FROM devices').fetchall() if True else []
            last_seen = {r['mac']: r['last_seen_at_ms'] for r in devs}
        finally:
            db.close()
        return anchors, last_seen

    def refresh_if_needed(self):
        now = int(time.time()*1000)
        if not self._cache or (now - self._ts) > self.refresh_ms:
            anchors, last_seen = self._read_db()
            self._cache = (anchors, last_seen)
            self._ts = now

    def get_anchor_positions(self) -> Dict[str, Tuple[float,float,float]]:
        self.refresh_if_needed()
        return self._cache[0] if self._cache else {}

    def is_online(self, anchor_mac:str) -> bool:
        self.refresh_if_needed()
        last_seen = self._cache[1] if self._cache else {}
        ts = last_seen.get(anchor_mac)
        if not ts: return False
        return (int(time.time()*1000) - ts) <= self.online_window_ms
