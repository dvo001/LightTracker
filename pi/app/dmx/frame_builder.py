def u16_to_coarse_fine(val: int):
    v = max(0, min(65535, int(val)))
    coarse = (v >> 8) & 0xFF
    fine = v & 0xFF
    return coarse, fine


def deg_to_u16(deg: float, min_deg: float, max_deg: float):
    if max_deg <= min_deg:
        return 0
    clamped = max(min_deg, min(max_deg, deg))
    span = max_deg - min_deg
    norm = (clamped - min_deg) / span
    return int(norm * 65535)


def build_frame(fixtures_commands, profiles):
    universe = bytearray(513)
    universe[0] = 0x00  # start code

    for cmd in fixtures_commands:
        channel_values = cmd.get("channel_values") if isinstance(cmd, dict) else None
        if channel_values:
            for ch, val in channel_values.items():
                if ch < 1 or ch > 512:
                    continue
                universe[ch] = max(0, min(255, int(val)))
            continue
        base = int(cmd["dmx_base_addr"])
        profile_key = cmd["profile_key"]
        profile = profiles.get(profile_key, {})
        pan_u16 = cmd["pan_u16"]
        tilt_u16 = cmd["tilt_u16"]
        pan_coarse, pan_fine = u16_to_coarse_fine(pan_u16)
        tilt_coarse, tilt_fine = u16_to_coarse_fine(tilt_u16)

        channels = profile.get("channels", 4)
        if base < 1 or base + channels - 1 > 512:
            continue

        ch_pan_c = base
        ch_pan_f = base + 1
        ch_tilt_c = base + 2
        ch_tilt_f = base + 3
        if ch_pan_f <= 512:
            universe[ch_pan_c] = pan_coarse
            universe[ch_pan_f] = pan_fine
        if ch_tilt_f <= 512:
            universe[ch_tilt_c] = tilt_coarse
            universe[ch_tilt_f] = tilt_fine

    return bytes(universe)
