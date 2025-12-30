import time
from app.core.range_cache import get_range_cache


def test_update_and_snapshot():
    rc = get_range_cache()
    # ensure clean state by using a unique tag
    tag = f"T{int(time.time()*1000)}"
    batch = {"anchor_mac": "A1", "ts_ms": int(time.time()*1000), "ranges": [{"tag_mac": tag, "d_m": 1.23}]}
    rc.update_from_batch(batch)
    snaps = rc.snapshot(tag, max_age_ms=1000)
    assert len(snaps) == 1
    assert snaps[0].anchor_mac == 'A1'

def test_snapshot_stale():
    rc = get_range_cache()
    tag = f"T{int(time.time()*1000)}"
    batch = {"anchor_mac": "A2", "ts_ms": int(time.time()*1000) - 5000, "ranges": [{"tag_mac": tag, "d_m": 2.0}]}
    rc.update_from_batch(batch)
    snaps = rc.snapshot(tag, max_age_ms=1000)
    assert len(snaps) == 0
