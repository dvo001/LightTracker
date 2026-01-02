from app.core.range_cache import RangeCache
import time


def test_range_cache_latest_per_anchor():
    rc = RangeCache(window_ms=500)
    now = int(time.time() * 1000)
    rc.update_from_batch("A1", now, [{"tag_mac": "T1", "d_m": 3.0, "ts_ms": now - 100}])
    rc.update_from_batch("A1", now + 10, [{"tag_mac": "T1", "d_m": 2.0, "ts_ms": now + 10}])
    snap = rc.snapshot("T1")
    assert len(snap) == 1
    assert snap[0].d_m == 2.0


def test_range_cache_stale_filtered():
    rc = RangeCache(window_ms=100)
    now = int(time.time() * 1000)
    rc.update_from_batch("A1", now - 200, [{"tag_mac": "T1", "d_m": 3.0, "ts_ms": now - 200}])
    snap = rc.snapshot("T1", max_age_ms=100)
    assert snap == []
