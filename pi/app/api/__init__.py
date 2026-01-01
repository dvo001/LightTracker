from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

from . import routes_state, routes_anchors, routes_fixtures, routes_calibration  # noqa: F401

router.include_router(routes_state.router)
router.include_router(routes_anchors.router)
router.include_router(routes_fixtures.router)
router.include_router(routes_calibration.router)
