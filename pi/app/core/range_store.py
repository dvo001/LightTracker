import time
from collections import deque, defaultdict
from typing import Dict, Deque, Any, List

class RangeSample:
    def __init__(self, ts_ms:int, distance_mm:float, quality:float=None, rssi:int=None):
        self.ts_ms = ts_ms
        self.distance_mm = distance_mm
        self.quality = quality
        self.rssi = rssi

class RangeStore:
    def __init__(self, window_ms:int=1500, max_samples_per_pair:int=30):
        self.window_ms = window_ms
        self.max_samples_per_pair = max_samples_per_pair
        # structure: ranges[tag_mac][anchor_mac] = deque[RangeSample]
        self.ranges = defaultdict(lambda: defaultdict(deque))

    def add_sample(self, tag_mac:str, anchor_mac:str, sample:RangeSample):
        dq = self.ranges[tag_mac][anchor_mac]
        dq.append(sample)
        # trim
        now = sample.ts_ms
        while dq and len(dq) > self.max_samples_per_pair:
            dq.popleft()
        # window trim
        while dq and (now - dq[0].ts_ms) > self.window_ms:
            dq.popleft()

    def add_range_batch(self, anchor_mac:str, ts_ms:int, ranges:List[dict]):
        for r in ranges:
            tag = r.get('tag_mac')
            # tolerate d_m or distance_mm
            dist_mm = r.get('distance_mm')
            if dist_mm is None and r.get('d_m') is not None:
                try:
                    dist_mm = float(r.get('d_m')) * 1000.0
                except Exception:
                    dist_mm = None
            if not tag or dist_mm is None:
                continue
            sample = RangeSample(ts_ms=int(r.get('ts_ms', ts_ms)), distance_mm=float(dist_mm), quality=r.get('quality'), rssi=r.get('rssi'))
            self.add_sample(tag, anchor_mac, sample)

    def snapshot_tag(self, tag_mac:str):
        # return dict anchor_mac -> median distance_mm
        import statistics
        res = {}
        for anchor, dq in self.ranges.get(tag_mac, {}).items():
            if not dq: continue
            vals = [s.distance_mm for s in dq]
            try:
                med = statistics.median(vals)
            except Exception:
                med = vals[len(vals)//2]
            res[anchor] = med
        return res
