import asyncio
import time
from typing import Dict, Any
from .range_store import RangeStore
from .anchor_cache import AnchorCache
from .solver import solve_position_3d

class TrackingEngine:
    def __init__(self, settings:Dict[str,Any]=None):
        s = settings or {}
        self.settings = s
        self.range_store = RangeStore(window_ms=s.get('tracking.window_ms',1500), max_samples_per_pair=s.get('tracking.max_samples_per_pair',30))
        self.anchor_cache = AnchorCache(refresh_ms=s.get('anchor_cache_refresh_ms',1000), online_window_ms=s.get('anchors.online_window_ms',8000))
        self.latest_position = {}
        self.latest_good_position = {}
        self._task = None
        self._running = False

    def enqueue_range_batch(self, anchor_mac:str, ts_ms:int, ranges:list):
        # called from mqtt callback
        self.range_store.add_range_batch(anchor_mac, ts_ms, ranges)

    async def run(self, loop_interval_ms:int=100):
        self._running = True
        while self._running:
            try:
                await self._solve_pass()
            except Exception:
                pass
            await asyncio.sleep(loop_interval_ms/1000.0)

    async def _solve_pass(self):
        # iterate known tags
        tags = list(self.range_store.ranges.keys())
        for tag in tags:
            dists = self.range_store.snapshot_tag(tag)
            if not dists:
                continue
            anchors_pos = self.anchor_cache.get_anchor_positions()
            # filter anchors that are known and online
            usable = {a:dist for a,dist in dists.items() if a in anchors_pos and self.anchor_cache.is_online(a)}
            if len(usable) < self.settings.get('tracking.min_anchors',4):
                # mark as no-fix
                self.latest_position[tag] = {'state':'NO_FIX','ts_ms':int(time.time()*1000)}
                continue
            res = solve_position_3d(anchors_pos, usable, max_iters=self.settings.get('tracking.max_iters',20), tol=self.settings.get('tracking.tol',1e-3))
            if not res:
                self.latest_position[tag] = {'state':'NO_FIX','ts_ms':int(time.time()*1000)}
                continue
            quality = 1.0 - min(res['residual_rms_mm']/self.settings.get('tracking.residual_max_mm',900),1.0)
            payload = {
                'pos_cm': {'x': res['pos_cm'][0], 'y': res['pos_cm'][1], 'z': res['pos_cm'][2]},
                'residual_rms_mm': res['residual_rms_mm'],
                'anchors_used': res['anchors_used'],
                'quality': max(0.0, min(1.0, quality)),
                'state': 'TRACKING_OK',
                'ts_ms': int(time.time()*1000)
            }
            self.latest_position[tag] = payload
            if payload['quality'] > 0.5:
                self.latest_good_position[tag] = payload

    def stop(self):
        self._running = False
