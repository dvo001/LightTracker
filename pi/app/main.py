import threading
import time
import logging

from fastapi import FastAPI

from app.db.persistence import get_persistence
from app.mqtt.mqtt_manager import MQTTManager
from app.core.tracking_engine import TrackingEngine
from app.api import routes_state, routes_settings, routes_devices, routes_events
from app.api import routes_calibration, routes_anchors
from app.api import routes_tracking

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pi.app")

app = FastAPI(title="LightTracker PI API")

app.include_router(routes_state.router, prefix="/api/v1")
app.include_router(routes_settings.router, prefix="/api/v1")
app.include_router(routes_devices.router, prefix="/api/v1")
app.include_router(routes_events.router, prefix="/api/v1")
app.include_router(routes_tracking.router, prefix="/api/v1")
app.include_router(routes_calibration.router, prefix="/api/v1")
app.include_router(routes_anchors.router, prefix="/api/v1")


@app.on_event("startup")
def startup_event():
    logger.info("Starting app: running migrations and starting MQTT")
    persistence = get_persistence()
    try:
        persistence.migrate()
    except Exception:
        logger.exception("Migration failed")
        raise

    # start MQTT manager
    mqtt_mgr = MQTTManager(persistence=persistence)
    thread = threading.Thread(target=mqtt_mgr.run, daemon=True, name="mqtt-manager")
    thread.start()
    # store manager for potential later use
    app.state.mqtt_manager = mqtt_mgr
    # start tracking engine
    tracking = TrackingEngine(persistence=persistence, mqtt_client=mqtt_mgr)
    tracking.start()
    app.state.tracking_engine = tracking


@app.on_event("shutdown")
def shutdown_event():
    logger.info("Shutting down app")
    mqtt_mgr = getattr(app.state, "mqtt_manager", None)
    if mqtt_mgr:
        mqtt_mgr.stop()
# FastAPI entrypoint
