import asyncio
import math
from app.core.tracking_engine import TrackingEngine


def _make_ranges_for_target(anchor_positions, target_cm):
    ranges = {}
    for mac, pos in anchor_positions.items():
        dx = target_cm[0] - pos[0]
        dy = target_cm[1] - pos[1]
        dz = target_cm[2] - pos[2]
        d_m = math.sqrt(dx * dx + dy * dy + dz * dz) / 100.0
        ranges[mac] = d_m
    return ranges


def test_tracking_engine_tracks():
    anchors = {
        "A": (0.0, 0.0, 0.0),
        "B": (100.0, 0.0, 0.0),
        "C": (0.0, 100.0, 0.0),
        "D": (0.0, 0.0, 100.0),
    }
    target = (50.0, 50.0, 50.0)

    te = TrackingEngine(anchor_positions_provider=lambda: anchors)
    # enqueue synthetic ranges per anchor
    for mac, d_m in _make_ranges_for_target(anchors, target).items():
        te.enqueue_range_batch(mac, 0, [{"tag_mac": "T1", "d_m": d_m}])

    asyncio.run(te._tick())
    p = te.latest_position.get("T1")
    assert p is not None
    assert p.get("state") == "TRACKING"
    pos = p.get("position_cm")
    assert pos
    assert abs(pos["x"] - target[0]) < 2.0
