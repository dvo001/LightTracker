from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

from . import routes_state, routes_anchors, routes_fixtures, routes_calibration, routes_health, routes_tracking, routes_settings, routes_devices, routes_events, routes_dmx, routes_ofl  # noqa: F401

router.include_router(routes_state.router)
router.include_router(routes_anchors.router)
router.include_router(routes_fixtures.router)
router.include_router(routes_calibration.router)
router.include_router(routes_health.router)
router.include_router(routes_tracking.router)
router.include_router(routes_settings.router)
router.include_router(routes_devices.router)
router.include_router(routes_events.router)
router.include_router(routes_dmx.router)
router.include_router(routes_ofl.router)
