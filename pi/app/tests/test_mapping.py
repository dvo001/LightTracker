import math
from app.dmx.mapping import compute_pan_tilt, limit


def test_compute_pan_tilt_basic():
    fx = {"x": 0, "y": 0, "z": 0}
    target = {"x": 100, "y": 0, "z": 0}
    pan, tilt = compute_pan_tilt(fx, target, {})
    assert abs(pan) < 1
    assert abs(tilt) < 1


def test_slew_limit():
    out = limit(0, 90, max_deg_per_s=45, dt_s=1)
    assert abs(out - 45) < 1e-3
