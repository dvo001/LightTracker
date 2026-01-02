import math
from typing import Dict, Tuple, List, Optional

def solve_position_3d(anchor_positions_cm: Dict[str, Tuple[float,float,float]], distances_mm: Dict[str, float], initial_guess_cm: Optional[Tuple[float,float,float]]=None, max_iters:int=20, tol:float=1e-3):
    # prepare lists
    keys = [k for k in distances_mm.keys() if k in anchor_positions_cm]
    if len(keys) < 4:
        return None

    anchors = [anchor_positions_cm[k] for k in keys]
    dists = [distances_mm[k]/10.0 for k in keys]  # mm -> cm

    # initial guess: centroid
    if initial_guess_cm:
        x = list(initial_guess_cm)
    else:
        x = [sum(p[i] for p in anchors)/len(anchors) for i in range(3)]

    for it in range(max_iters):
        JtJ = [[0.0]*3 for _ in range(3)]
        Jtr = [0.0]*3
        valid = 0
        residuals = []
        for (xi,yi,zi), ri in zip(anchors, dists):
            dx = x[0]-xi; dy = x[1]-yi; dz = x[2]-zi
            pred = math.hypot(math.hypot(dx,dy), dz)
            if pred == 0:
                continue
            r = pred - ri
            residuals.append(r)
            # jacobian row
            j = [dx/pred, dy/pred, dz/pred]
            # accumulate JtJ and Jtr
            for a in range(3):
                for b in range(3):
                    JtJ[a][b] += j[a]*j[b]
                Jtr[a] += j[a]*r
            valid += 1

        if valid < 4:
            return None

        # solve 3x3 linear system JtJ * delta = -Jtr
        # use Cramer's rule
        def det3(m):
            return (m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1]) - m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0]) + m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]))

        D = det3(JtJ)
        if abs(D) < 1e-12:
            return None

        # build RHS
        rhs = [-v for v in Jtr]
        # matrices for determinants
        def replace_col(mat, col_idx, vec):
            m = [list(row) for row in mat]
            for i in range(3): m[i][col_idx] = vec[i]
            return m

        Dx = det3(replace_col(JtJ, 0, rhs))
        Dy = det3(replace_col(JtJ, 1, rhs))
        Dz = det3(replace_col(JtJ, 2, rhs))

        delta = [Dx/D, Dy/D, Dz/D]
        # update
        x = [x[i] + delta[i] for i in range(3)]
        step = math.hypot(math.hypot(delta[0], delta[1]), delta[2])
        if step < tol:
            break

    # compute residual rms in mm
    rms = 0.0
    for (xi,yi,zi), ri in zip(anchors, dists):
        pred = math.hypot(math.hypot(x[0]-xi, x[1]-yi), x[2]-zi)
        r = (pred - ri)*10.0
        rms += r*r
    rms = math.sqrt(rms/len(anchors)) if anchors else float('inf')

    return {
        'pos_cm': (x[0], x[1], x[2]),
        'residual_rms_mm': rms,
        'anchors_used': keys
    }
