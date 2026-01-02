import threading
import time
from typing import Dict, List, Optional, Tuple


class RangeSample:
    def __init__(self, anchor_mac: str, tag_mac: str, d_m: float, ts_ms: int, quality: Optional[float] = None):
        self.anchor_mac = anchor_mac
        self.tag_mac = tag_mac
        self.d_m = d_m
        self.ts_ms = ts_ms
        self.quality = quality


class RangeCache:
    """Thread-safe cache for latest range samples per (tag, anchor)."""

    def __init__(self, window_ms: int = 1500):
        self.window_ms = window_ms
        self._samples: Dict[Tuple[str, str], RangeSample] = {}
        self._lock = threading.Lock()

    def update_from_batch(self, anchor_mac: str, batch_ts_ms: int, ranges: List[dict]):
        now_ms = int(time.time() * 1000)
        ts = batch_ts_ms or now_ms
        with self._lock:
            for r in ranges:
                tag = r.get("tag_mac")
                d_m = r.get("d_m")
                if d_m is None:
                    # tolerate distance_mm
                    if r.get("distance_mm") is not None:
                        d_m = float(r.get("distance_mm")) / 1000.0
                if not tag or d_m is None:
                    continue
                rs = RangeSample(anchor_mac, tag, float(d_m), int(r.get("ts_ms", ts)), r.get("q"))
                key = (tag, anchor_mac)
                self._samples[key] = rs
            self._prune_locked(now_ms)

    def _prune_locked(self, now_ms: int):
        cutoff = now_ms - self.window_ms
        self._samples = {k: v for k, v in self._samples.items() if v.ts_ms >= cutoff}

    def snapshot(self, tag_mac: str, max_age_ms: Optional[int] = None) -> List[RangeSample]:
        now_ms = int(time.time() * 1000)
        cutoff = now_ms - (max_age_ms if max_age_ms is not None else self.window_ms)
        with self._lock:
            res = [v for (tag, _), v in self._samples.items() if tag == tag_mac and v.ts_ms >= cutoff]
        # keep only latest per anchor
        latest: Dict[str, RangeSample] = {}
        for s in res:
            prev = latest.get(s.anchor_mac)
            if (prev is None) or (s.ts_ms > prev.ts_ms):
                latest[s.anchor_mac] = s
        return list(latest.values())
