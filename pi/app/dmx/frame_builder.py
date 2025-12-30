def u16_to_coarse_fine(v: int):
    v = max(0, min(65535, int(v)))
    hi = (v >> 8) & 0xFF
    lo = v & 0xFF
    return hi, lo


def deg_to_u16(value_deg, min_deg, max_deg):
    # linear mapping min_deg -> 0, max_deg -> 65535
    if max_deg == min_deg:
        return 0
    frac = (value_deg - min_deg) / (max_deg - min_deg)
    frac = max(0.0, min(1.0, frac))
    return int(frac * 65535)


def build_frame(fixtures_commands, profiles) -> bytes:
    # build 513-byte DMX packet (startcode + 512 channels)
    frame = bytearray(513)
    frame[0] = 0x00
    # for each fixture, map channels
    for f in fixtures_commands:
        base = int(f.get('dmx_base_addr', 1))
        # profile mapping: assume pan coarse,fine, tilt coarse,fine at offsets 0..3
        pan_v = f.get('pan_u16', 0)
        tilt_v = f.get('tilt_u16', 0)
        hi, lo = u16_to_coarse_fine(pan_v)
        th, tl = u16_to_coarse_fine(tilt_v)
        channel_count = 4
        if base < 1 or base + channel_count - 1 > 512:
            continue
        idx = base
        frame[idx] = hi
        frame[idx+1] = lo
        frame[idx+2] = th
        frame[idx+3] = tl
    return bytes(frame)
# DMX frame builder
