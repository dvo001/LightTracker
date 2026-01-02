import math


def _wrap_shortest(current: float, target: float) -> float:
    delta = (target - current + 180) % 360 - 180
    return current + delta


def limit(prev_deg: float, target_deg: float, max_deg_per_s: float, dt_s: float) -> float:
    if max_deg_per_s <= 0 or dt_s <= 0:
        return target_deg
    max_step = max_deg_per_s * dt_s
    delta = target_deg - prev_deg
    if abs(delta) <= max_step:
        return target_deg
    return prev_deg + max_step * (1 if delta > 0 else -1)


def compute_pan_tilt(fixture_pos_cm, target_pos_cm, cfg):
    vx = target_pos_cm["x"] - fixture_pos_cm["x"]
    vy = target_pos_cm["y"] - fixture_pos_cm["y"]
    vz = target_pos_cm["z"] - fixture_pos_cm["z"]
    pan = math.degrees(math.atan2(vy, vx))
    hyp = math.sqrt(vx * vx + vy * vy)
    tilt = math.degrees(math.atan2(vz, hyp))

    pan = _wrap_shortest(cfg.get("pan_zero_deg", 0), pan + cfg.get("pan_offset_deg", 0))
    tilt = tilt + cfg.get("tilt_offset_deg", 0) + cfg.get("tilt_zero_deg", 0)

    if cfg.get("invert_pan"):
        pan = -pan
    if cfg.get("invert_tilt"):
        tilt = -tilt

    pan = max(cfg.get("pan_min_deg", -360), min(cfg.get("pan_max_deg", 360), pan))
    tilt = max(cfg.get("tilt_min_deg", -180), min(cfg.get("tilt_max_deg", 180), tilt))
    return pan, tilt
