import math


def compute_pan_tilt(fixture_pos_cm, target_pos_cm):
    vx = target_pos_cm[0] - fixture_pos_cm[0]
    vy = target_pos_cm[1] - fixture_pos_cm[1]
    vz = target_pos_cm[2] - fixture_pos_cm[2]
    pan = math.degrees(math.atan2(vy, vx))
    horiz = math.hypot(vx, vy)
    tilt = math.degrees(math.atan2(vz, horiz))
    return pan, tilt


def apply_limits_and_offsets(pan_deg, tilt_deg, fixture):
    # fixture: dict with invert, offsets, zeros, min/max
    if fixture.get('invert_pan'):
        pan_deg = -pan_deg
    if fixture.get('invert_tilt'):
        tilt_deg = -tilt_deg

    pan_deg = pan_deg + fixture.get('pan_offset_deg', 0) - fixture.get('pan_zero_deg', 0)
    tilt_deg = tilt_deg + fixture.get('tilt_offset_deg', 0) - fixture.get('tilt_zero_deg', 0)

    # wrap pan to [-180,180]
    pan_deg = ((pan_deg + 180) % 360) - 180

    # clamp
    pan_min = fixture.get('pan_min_deg', -180)
    pan_max = fixture.get('pan_max_deg', 180)
    tilt_min = fixture.get('tilt_min_deg', -90)
    tilt_max = fixture.get('tilt_max_deg', 90)

    pan_deg = max(min(pan_deg, pan_max), pan_min)
    tilt_deg = max(min(tilt_deg, tilt_max), tilt_min)
    return pan_deg, tilt_deg


def limit(prev_deg, target_deg, max_deg_per_s, dt_s):
    if max_deg_per_s is None or max_deg_per_s <= 0:
        return target_deg
    max_step = max_deg_per_s * dt_s
    delta = target_deg - prev_deg
    # wrap shortest for pan-like values
    if abs(delta) > 180:
        if delta > 0:
            delta = delta - 360
        else:
            delta = delta + 360
    if delta > max_step:
        delta = max_step
    if delta < -max_step:
        delta = -max_step
    new = prev_deg + delta
    return new
# Pan/Tilt mapping math
