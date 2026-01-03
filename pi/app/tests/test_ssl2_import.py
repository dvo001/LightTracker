from app.dmx.ssl2_import import parse_ssl2_fixture


def test_parse_ssl2_basic():
    xml = b"""
    <Fixture Name="TestMover">
      <Channels>
        <Channel Name="Pan" />
        <Channel Name="Pan Fine" />
        <Channel Name="Tilt" />
        <Channel Name="Tilt Fine" />
        <Channel Name="Dimmer" />
      </Channels>
    </Fixture>
    """
    key, profile = parse_ssl2_fixture(xml, filename="mover.ssl2")
    assert key == "testmover"
    assert profile["channels"] == 5
    assert profile["pan_coarse"] == 1
    assert profile["pan_fine"] == 2
    assert profile["tilt_coarse"] == 3
    assert profile["tilt_fine"] == 4
