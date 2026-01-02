import math
from typing import Dict, List, Optional, Tuple


class TrilaterationResult:
    def __init__(self, pos_cm: Optional[Tuple[float, float, float]], anchors_used: List[str], resid_m: float, iterations: int, outliers: List[str], reason: Optional[str] = None):
        self.pos_cm = pos_cm
        self.anchors_used = anchors_used
        self.resid_m = resid_m
        self.iterations = iterations
        self.outliers = outliers
        self.reason = reason


def solve_3d(anchor_positions_cm: Dict[str, Tuple[float, float, float]], samples: Dict[str, float], initial_pos_cm: Optional[Tuple[float, float, float]] = None, max_iter: int = 12, eps_step_cm: float = 0.2, resid_max_m: float = 5.0, d_min_cm: float = 1.0, d_max_cm: float = 200000.0, allow_outlier: bool = True) -> TrilaterationResult:
    """Weighted least squares / LM style solver, minimal but deterministic."""
    anchors = []
    dists_cm = []
    keys = []
    for mac, dist_cm in samples.items():
        if mac not in anchor_positions_cm:
            continue
        dc = dist_cm
        if dc < d_min_cm or dc > d_max_cm:
            continue
        anchors.append(anchor_positions_cm[mac])
        dists_cm.append(dc)
        keys.append(mac)

    if len(anchors) < 4:
        return TrilaterationResult(None, keys, float("inf"), 0, [], "insufficient_anchors")

    if initial_pos_cm:
        x = list(initial_pos_cm)
    else:
        x = [sum(p[i] for p in anchors) / len(anchors) for i in range(3)]

    lam = 1e-3
    outliers: List[str] = []
    it = 0
    last_rms = float("inf")

    while it < max_iter:
        it += 1
        JtJ = [[0.0] * 3 for _ in range(3)]
        Jtr = [0.0] * 3
        residuals = []
        for (ax, ay, az), d in zip(anchors, dists_cm):
            dx = x[0] - ax
            dy = x[1] - ay
            dz = x[2] - az
            pred = math.sqrt(dx * dx + dy * dy + dz * dz)
            if pred == 0:
                continue
            r = pred - d
            residuals.append(r)
            j = [dx / pred, dy / pred, dz / pred]
            for a in range(3):
                for b in range(3):
                    JtJ[a][b] += j[a] * j[b]
                Jtr[a] += j[a] * r

        if len(residuals) < 4:
            return TrilaterationResult(None, keys, float("inf"), it, outliers, "insufficient_residuals")

        # damping
        for i in range(3):
            JtJ[i][i] += lam

        def det3(m):
            return (
                m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
                - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
            )

        D = det3(JtJ)
        if abs(D) < 1e-12:
            return TrilaterationResult(None, keys, float("inf"), it, outliers, "singular")

        rhs = [-v for v in Jtr]

        def replace_col(mat, col_idx, vec):
            m = [list(row) for row in mat]
            for i in range(3):
                m[i][col_idx] = vec[i]
            return m

        Dx = det3(replace_col(JtJ, 0, rhs))
        Dy = det3(replace_col(JtJ, 1, rhs))
        Dz = det3(replace_col(JtJ, 2, rhs))

        delta = [Dx / D, Dy / D, Dz / D]
        x = [x[i] + delta[i] for i in range(3)]
        step = math.sqrt(delta[0] * delta[0] + delta[1] * delta[1] + delta[2] * delta[2])
        if step < eps_step_cm:
            break

        rms_cm = math.sqrt(sum(r * r for r in residuals) / len(residuals))
        if rms_cm / 100.0 < resid_max_m:
            last_rms = rms_cm

        if rms_cm > last_rms * 1.5 and allow_outlier and len(keys) > 4:
            # drop worst anchor once
            worst_idx = max(range(len(residuals)), key=lambda i: abs(residuals[i]))
            outliers.append(keys.pop(worst_idx))
            anchors.pop(worst_idx)
            dists_cm.pop(worst_idx)
            allow_outlier = False

    # final residual
    rms_cm = 0.0
    for (ax, ay, az), d in zip(anchors, dists_cm):
        dx = x[0] - ax
        dy = x[1] - ay
        dz = x[2] - az
        pred = math.sqrt(dx * dx + dy * dy + dz * dz)
        rms_cm += (pred - d) * (pred - d)
    rms_cm = math.sqrt(rms_cm / len(anchors))
    resid_m = rms_cm / 100.0
    if resid_m > resid_max_m:
        return TrilaterationResult(None, keys, resid_m, it, outliers, "resid_gated")

    return TrilaterationResult((x[0], x[1], x[2]), keys, resid_m, it, outliers, None)
