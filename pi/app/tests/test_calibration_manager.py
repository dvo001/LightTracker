from app.core.calibration_manager import CalibrationManager
from app.core.range_cache import RangeCache


def test_calibration_manager_simple():
    rc = RangeCache()
    cm = CalibrationManager(rc)
    run_id = cm.start("T1", 100)
    assert run_id is not None
    # feed sample
    rc.update_from_batch("A1", 0, [{"tag_mac": "T1", "d_m": 3.0}])
    cm.tick()
    cm.abort()
    assert cm.active is None
