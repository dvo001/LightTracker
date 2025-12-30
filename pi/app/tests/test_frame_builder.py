from app.dmx.frame_builder import u16_to_coarse_fine, deg_to_u16, build_frame


def test_u16_split():
    hi, lo = u16_to_coarse_fine(65535)
    assert hi == 255 and lo == 255


def test_deg_to_u16():
    v = deg_to_u16(0, -180, 180)
    assert v == 32767 or v == 32768


def test_build_frame_len():
    fixtures = [{'dmx_base_addr': 1, 'pan_u16': 1000, 'tilt_u16': 2000}]
    frame = build_frame(fixtures, None)
    assert len(frame) == 513
