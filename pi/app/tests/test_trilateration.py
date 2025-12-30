import numpy as np
from app.core.trilateration import solve_3d


def test_trilateration_simple():
    # anchors at cube corners (cm)
    anchors = {
        'A1': (0.0, 0.0, 0.0),
        'A2': (100.0, 0.0, 0.0),
        'A3': (0.0, 100.0, 0.0),
        'A4': (0.0, 0.0, 100.0),
    }
    # true position (cm)
    true = np.array([30.0, 40.0, 20.0])
    # distances in meters
    samples = []
    class S: pass
    for k, p in anchors.items():
        s = S()
        s.anchor_mac = k
        s.d_m = np.linalg.norm(true - np.array(p)) / 100.0
        samples.append(s)

    res = solve_3d(anchors, samples)
    assert res.pos_cm is not None
    est = np.array(res.pos_cm)
    err = np.linalg.norm(est - true)
    assert err < 5.0  # within 5 cm
