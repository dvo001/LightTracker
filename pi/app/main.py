import threading
import time
import logging

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

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

# --- Web UI integration (Jinja2 + static files)
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

static_dir = str(BASE_DIR / "web" / "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# UI routes
@app.get("/ui")
def ui_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/ui/anchors")
def ui_anchors(request: Request):
    return templates.TemplateResponse("anchors.html", {"request": request})


@app.get("/ui/fixtures")
def ui_fixtures(request: Request):
    return templates.TemplateResponse("fixtures.html", {"request": request})


@app.get("/ui/fixtures/new")
def ui_fixture_new(request: Request):
    return templates.TemplateResponse("fixture_new.html", {"request": request})


@app.get("/ui/fixtures/{fixture_id}/edit")
def ui_fixture_edit(request: Request, fixture_id: int):
    return templates.TemplateResponse("fixture_edit.html", {"request": request, "fixture_id": fixture_id})


@app.get("/ui/calibration")
def ui_calibration(request: Request):
    return templates.TemplateResponse("calibration.html", {"request": request})


@app.get("/ui/live")
def ui_live(request: Request):
    return templates.TemplateResponse("live.html", {"request": request})


@app.get("/ui/logs")
def ui_logs(request: Request):
    return templates.TemplateResponse("logs.html", {"request": request})


@app.get("/ui/settings")
def ui_settings(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request})


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
