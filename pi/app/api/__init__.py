from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

from . import routes_state, routes_anchors, routes_fixtures, routes_calibration, routes_health, routes_tracking  # noqa: F401

router.include_router(routes_state.router)
router.include_router(routes_anchors.router)
router.include_router(routes_fixtures.router)
router.include_router(routes_calibration.router)
router.include_router(routes_health.router)
router.include_router(routes_tracking.router)
