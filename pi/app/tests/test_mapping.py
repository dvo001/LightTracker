from app.dmx.mapping import compute_pan_tilt, apply_limits_and_offsets, limit
import math


def test_quadrants():
    f = (0,0,0)
    # +X axis
    p,t = compute_pan_tilt(f, (100,0,0))
    assert abs(p - 0) < 1e-6
    # +Y axis
    p,t = compute_pan_tilt(f, (0,100,0))
    assert abs(p - 90) < 1e-6
    # +Z up
    p,t = compute_pan_tilt(f, (0,0,100))
    assert abs(t - 90) < 1e-6


def test_limit_and_wrap():
    prev = 170
    target = -170
    new = limit(prev, target, 20, 1.0)
    # shortest delta is 20 deg towards -170 (wrap), so step limited
    assert abs(new - 150) < 1e-6
