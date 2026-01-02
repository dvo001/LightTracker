from app.core.trilateration import solve_3d
import math


def test_trilateration_basic():
    anchors = {
        "A": (0.0, 0.0, 0.0),
        "B": (100.0, 0.0, 0.0),
        "C": (0.0, 100.0, 0.0),
        "D": (0.0, 0.0, 100.0),
    }
    # target at (50,50,50) cm
    target = (50.0, 50.0, 50.0)
    dists = {}
    for k, p in anchors.items():
        dx = target[0] - p[0]
        dy = target[1] - p[1]
        dz = target[2] - p[2]
        dists[k] = math.sqrt(dx * dx + dy * dy + dz * dz)
    res = solve_3d(anchors, dists, resid_max_m=2.0)
    assert res.pos_cm is not None
    assert all(abs(res.pos_cm[i] - target[i]) < 1.0 for i in range(3))
    assert res.resid_m < 0.05
