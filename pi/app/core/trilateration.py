from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import numpy as np


@dataclass
class TrilaterationResult:
    pos_cm: Optional[np.ndarray]
    anchors_used: int
    resid_m: Optional[float]
    iterations: int
    outliers: List[str]
    reason: Optional[str]


def solve_3d(anchor_positions_cm: Dict[str, Tuple[float, float, float]], samples: List[Any], initial_pos_cm: Optional[Tuple[float, float, float]] = None, *, min_anchors: int = 4, max_iter: int = 12, eps_step_cm: float = 0.2, resid_max_m: float = 1.0) -> TrilaterationResult:
    """Simple LM-based WLS trilateration.

    anchor_positions_cm: map mac->(x_cm,y_cm,z_cm)
    samples: list of objects with .anchor_mac and .d_m (meters)
    returns TrilaterationResult
    """
    # collect anchors with position
    A_keys = []
    A_pos = []
    d_cm = []
    for s in samples:
        a = s.anchor_mac
        if a in anchor_positions_cm:
            A_keys.append(a)
            A_pos.append(anchor_positions_cm[a])
            d_cm.append(s.d_m * 100.0)

    if len(A_keys) < min_anchors:
        return TrilaterationResult(pos_cm=None, anchors_used=len(A_keys), resid_m=None, iterations=0, outliers=[], reason="insufficient_anchors")

    A = np.array(A_pos, dtype=float)  # N x 3
    d = np.array(d_cm, dtype=float)   # N

    # initial guess: centroid of anchors or provided
    if initial_pos_cm is None:
        x = A.mean(axis=0)
    else:
        x = np.array(initial_pos_cm, dtype=float)

    lam = 1e-3
    outliers = []
    iterations = 0

    for it in range(max_iter):
        iterations = it + 1
        # distances
        diff = x - A  # N x 3
        r = np.linalg.norm(diff, axis=1)
        # residuals: predicted range - measured
        res = r - d
        # Jacobian J_ij = (x_j - a_ij) / r_i
        J = (diff / r[:, None])
        # weight matrix (identity for now)
        W = np.eye(len(d))
        # normal equations
        JTWJ = J.T @ W @ J
        g = J.T @ W @ res

        # damping for LM
        A_mat = JTWJ + lam * np.diag(np.diag(JTWJ) + 1e-6)
        try:
            dx = -np.linalg.solve(A_mat, g)
        except np.linalg.LinAlgError:
            return TrilaterationResult(pos_cm=None, anchors_used=len(A_keys), resid_m=float(np.sqrt((res**2).mean()))/100.0, iterations=iterations, outliers=outliers, reason='singular')

        if np.linalg.norm(dx) < eps_step_cm:
            x = x + dx
            break
        # try step
        x_new = x + dx
        # evaluate new residual
        r_new = np.linalg.norm(x_new - A, axis=1)
        res_new = r_new - d
        if np.linalg.norm(res_new) < np.linalg.norm(res):
            # accept and reduce lambda
            x = x_new
            lam = lam / 10.0
        else:
            lam = lam * 10.0

    # final residuals
    final_r = np.linalg.norm(x - A, axis=1)
    final_res = final_r - d
    resid_m = float(np.sqrt((final_res ** 2).mean()) / 100.0)

    # outlier gating
    worst_idx = int(np.argmax(np.abs(final_res)))
    worst_res_m = abs(final_res[worst_idx]) / 100.0
    if worst_res_m > resid_max_m and len(A_keys) >= (min_anchors + 1):
        # drop worst and retry once
        drop_key = A_keys[worst_idx]
        outliers.append(drop_key)
        # build reduced inputs
        mask = [i for i in range(len(A_keys)) if i != worst_idx]
        A2 = A[mask]
        d2 = d[mask]
        # rerun simple GN on reduced set
        try:
            x2 = x.copy()
            for it in range(max_iter):
                diff2 = x2 - A2
                r2 = np.linalg.norm(diff2, axis=1)
                res2 = r2 - d2
                J2 = (diff2 / r2[:, None])
                JTJ2 = J2.T @ J2
                g2 = J2.T @ res2
                try:
                    dx2 = -np.linalg.solve(JTJ2 + 1e-6 * np.eye(3), g2)
                except np.linalg.LinAlgError:
                    break
                x2 = x2 + dx2
                if np.linalg.norm(dx2) < eps_step_cm:
                    break
            x = x2
            final_r = np.linalg.norm(x - A2, axis=1)
            final_res = final_r - d2
            resid_m = float(np.sqrt((final_res ** 2).mean()) / 100.0)
        except Exception:
            return TrilaterationResult(pos_cm=None, anchors_used=len(A_keys), resid_m=None, iterations=iterations, outliers=outliers, reason='retry_failed')

    return TrilaterationResult(pos_cm=x, anchors_used=len(A_keys), resid_m=resid_m, iterations=iterations, outliers=outliers, reason=None)
# WLS/LM trilateration
