from app.dmx.frame_builder import build_frame, deg_to_u16, u16_to_coarse_fine


def test_frame_builder_length_and_channels():
    profiles = {"generic": {"channels": 4}}
    cmds = [{"profile_key": "generic", "dmx_base_addr": 1, "pan_u16": 65535, "tilt_u16": 0}]
    frame = build_frame(cmds, profiles)
    assert len(frame) == 513
    # pan coarse at channel 1 should be 255
    assert frame[1] == 255
    assert frame[2] == 255
    assert frame[3] == 0
    assert frame[4] == 0


def test_deg_to_u16():
    assert deg_to_u16(0, -90, 90) == 32767 or deg_to_u16(0, -90, 90) == 32768
    assert deg_to_u16(-90, -90, 90) == 0
    assert deg_to_u16(90, -90, 90) == 65535


def test_u16_coarse_fine():
    c, f = u16_to_coarse_fine(0xABCD)
    assert c == 0xAB and f == 0xCD
