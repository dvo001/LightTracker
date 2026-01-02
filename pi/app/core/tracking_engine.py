import asyncio
import time
from typing import Any, Callable, Dict, List, Optional

from .range_cache import RangeCache
from .trilateration import solve_3d


class TrackingEngine:
    def __init__(self, settings: Optional[Dict[str, Any]] = None, anchor_positions_provider: Optional[Callable[[], Dict[str, Any]]] = None, mqtt_publish: Optional[Callable[[str, dict], None]] = None):
        s = settings or {}
        self.settings = s
        self.range_cache = RangeCache(window_ms=s.get("tracking.window_ms", 1500))
        self.stale_timeout_ms = s.get("rates.global.stale_timeout_ms", s.get("stale_timeout_ms", 1500))
        self.lost_timeout_ms = s.get("rates.global.lost_timeout_ms", s.get("lost_timeout_ms", 4000))
        self.tracking_hz = s.get("rates.global.tracking_hz", s.get("tracking_hz", 10))
        self.anchor_positions_provider = anchor_positions_provider
        self.mqtt_publish = mqtt_publish
        self.latest_position: Dict[str, dict] = {}
        self._running = False

    def enqueue_range_batch(self, anchor_mac: str, ts_ms: int, ranges: List[dict]):
        self.range_cache.update_from_batch(anchor_mac, ts_ms, ranges)

    def _get_anchor_positions(self) -> Dict[str, Any]:
        if self.anchor_positions_provider:
            return self.anchor_positions_provider()
        # lazy import to avoid circular
        from app.db import connect_db
        db = connect_db()
        try:
            rows = db.execute("SELECT mac,x_cm,y_cm,z_cm FROM anchor_positions").fetchall()
            return {r["mac"]: (r["x_cm"], r["y_cm"], r["z_cm"]) for r in rows}
        finally:
            db.close()

    async def run(self):
        self._running = True
        interval = 1.0 / float(self.tracking_hz or 10)
        while self._running:
            try:
                await self._tick()
            except Exception:
                pass
            await asyncio.sleep(interval)

    async def _tick(self):
        anchors = self._get_anchor_positions()
        now_ms = int(time.time() * 1000)
        tags = self._tags_seen()
        for tag_mac in tags:
            samples = self.range_cache.snapshot(tag_mac, max_age_ms=self.stale_timeout_ms)
            # build dict anchor->dist_cm
            dist_map = {}
            for s in samples:
                if s.anchor_mac in anchors:
                    dist_map[s.anchor_mac] = s.d_m * 100.0  # m -> cm
            if len(dist_map) < 4:
                self._set_state(tag_mac, "STALE" if self._is_recent(tag_mac, now_ms) else "LOST", now_ms, None, anchors_used=[])
                continue
            res = solve_3d(anchors, dist_map, resid_max_m=self.settings.get("tracking.resid_max_m", 5.0))
            if res.pos_cm is None:
                self._set_state(tag_mac, "STALE" if self._is_recent(tag_mac, now_ms) else "LOST", now_ms, None, anchors_used=res.anchors_used, reason=res.reason)
                continue
            payload = {
                "tag_mac": tag_mac,
                "state": "TRACKING",
                "position_cm": {"x": res.pos_cm[0], "y": res.pos_cm[1], "z": res.pos_cm[2]},
                "anchors_used": res.anchors_used,
                "resid_m": res.resid_m,
                "outliers": res.outliers,
                "ts_ms": now_ms,
            }
            self.latest_position[tag_mac] = payload
            if self.mqtt_publish:
                try:
                    self.mqtt_publish(f"tracking/{tag_mac}/position", payload)
                except Exception:
                    pass

    def _tags_seen(self) -> List[str]:
        with self.range_cache._lock:
            return list({tag for (tag, _), _ in self.range_cache._samples.items()})

    def _is_recent(self, tag_mac: str, now_ms: int) -> bool:
        last = self.latest_position.get(tag_mac, {}).get("ts_ms")
        if last is None:
            return False
        return (now_ms - last) <= self.lost_timeout_ms

    def _set_state(self, tag_mac: str, state: str, now_ms: int, pos: Optional[dict], anchors_used: List[str], reason: Optional[str] = None):
        payload = self.latest_position.get(tag_mac, {}).copy()
        payload.update({
            "tag_mac": tag_mac,
            "state": state,
            "ts_ms": now_ms,
            "anchors_used": anchors_used,
        })
        if pos:
            payload["position_cm"] = pos
        if reason:
            payload["reason"] = reason
        self.latest_position[tag_mac] = payload

    def stop(self):
        self._running = False
