from dataclasses import dataclass
import threading
import time
from typing import Dict, Optional, Any, List


@dataclass
class RangeSample:
    tag_mac: str
    anchor_mac: str
    d_m: float
    ts_ms: int
    q: Optional[float] = None
    extra: Optional[Dict[str, Any]] = None


class RangeCache:
    """Thread-safe cache storing the latest sample per (tag,anchor).

    Usage:
      update_from_batch(batch_dict)
      snapshot(tag_mac, max_age_ms) -> List[RangeSample]
    """

    def __init__(self):
        self._lock = threading.RLock()
        # map tag_mac -> anchor_mac -> RangeSample
        self._data: Dict[str, Dict[str, RangeSample]] = {}

    def update_from_batch(self, batch: Dict[str, Any]):
        """Ingest a parsed range-batch. Expected tolerant schema:
        {
          "anchor_mac": "aa:...",
          "ts_ms": 12345,
          "ranges": [ {"tag_mac": "..", "d_m": 1.23, "q":0.9 }, ... ]
        }
        """
        try:
            anchor = batch.get("anchor_mac") or batch.get("anchor")
            ts_ms = batch.get("ts_ms") or int(time.time() * 1000)
            ranges = batch.get("ranges") or []
        except Exception:
            return

        with self._lock:
            for r in ranges:
                try:
                    tag = r.get("tag_mac") or r.get("tag")
                    d_m = float(r.get("d_m") if r.get("d_m") is not None else r.get("d"))
                    q = r.get("q")
                except Exception:
                    continue
                if not tag or d_m is None:
                    continue
                tag_map = self._data.setdefault(tag, {})
                existing = tag_map.get(anchor)
                sample = RangeSample(tag_mac=tag, anchor_mac=anchor, d_m=d_m, ts_ms=ts_ms, q=q, extra=r)
                # accept newest by ts_ms
                if existing is None or sample.ts_ms >= existing.ts_ms:
                    tag_map[anchor] = sample

    def snapshot(self, tag_mac: str, max_age_ms: int) -> List[RangeSample]:
        now = int(time.time() * 1000)
        with self._lock:
            tag_map = self._data.get(tag_mac, {})
            out: List[RangeSample] = []
            for anchor, s in tag_map.items():
                if now - s.ts_ms <= max_age_ms:
                    out.append(s)
            return out


# module-level singleton
_range_cache: Optional[RangeCache] = None


def get_range_cache() -> RangeCache:
    global _range_cache
    if _range_cache is None:
        _range_cache = RangeCache()
    return _range_cache

