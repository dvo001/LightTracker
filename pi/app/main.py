from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import threading
import asyncio
import json
import sys

from .db.migrations.runner import run_migrations
from .api import router as api_router

try:
    from app.db.persistence import get_persistence
    from app.api.routes_dmx import _load_dmx_config
except Exception:
    get_persistence = None
    _load_dmx_config = None

app = FastAPI()

BASE_DIR = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, 'web', 'templates'))
app.mount('/static', StaticFiles(directory=os.path.join(BASE_DIR, 'web', 'static')), name='static')

# cache-busting for static assets
try:
    APP_JS_VERSION = str(int(os.path.getmtime(os.path.join(BASE_DIR, 'web', 'static', 'app.js'))))
    APP_CSS_VERSION = str(int(os.path.getmtime(os.path.join(BASE_DIR, 'web', 'static', 'style.css'))))
except Exception:
    APP_JS_VERSION = APP_CSS_VERSION = "1"
templates.env.globals["app_js_version"] = APP_JS_VERSION
templates.env.globals["app_css_version"] = APP_CSS_VERSION


@app.on_event('startup')
def startup():
    loop = asyncio.get_event_loop()

    # Run migrations in a separate thread to avoid blocking startup in dev
    def _run():
        try:
            run_migrations()
        except Exception as e:
            print(f"[startup] migrations failed: {e}", file=sys.stderr)
    t = threading.Thread(target=_run, daemon=True)
    t.start()

    # initialize state for websocket clients and calibration
    app.state.ws_clients = set()
    app.state.active_calibration = None
    app.state.mqtt_ok = False
    # initialize tracking engine (lazy: may import paho later)
    try:
        from .core.tracking_engine import TrackingEngine
        te = TrackingEngine()
        app.state.tracking_engine = te
        try:
            loop.create_task(te.run())
        except Exception as e:
            print(f"[startup] tracking engine loop failed to start: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[startup] tracking engine init failed: {e}", file=sys.stderr)
        app.state.tracking_engine = None
    # start mqtt client (if available) and wire to tracking_engine
    try:
        from .mqtt_client import MQTTClientWrapper
        # prefer DB settings if available, fallback to env/defaults
        mqtt_host = os.environ.get('MQTT_HOST', 'localhost')
        mqtt_port = int(os.environ.get('MQTT_PORT', '1883'))
        if get_persistence:
            try:
                p = get_persistence()
                mqtt_host = p.get_setting('mqtt.host', mqtt_host) or mqtt_host
                mqtt_port = int(p.get_setting('mqtt.port', mqtt_port) or mqtt_port)
            except Exception:
                pass
        mc = MQTTClientWrapper(
            broker_host=mqtt_host,
            broker_port=mqtt_port,
            tracking_engine=app.state.tracking_engine,
            status_cb=lambda ok: setattr(app.state, "mqtt_ok", bool(ok))
        )
        app.state.mqtt_client = mc
        try:
            mc.start()
            app.state.mqtt_ok = mc.connected
        except Exception as e:
            print(f"[startup] mqtt start failed: {e}", file=sys.stderr)
            app.state.mqtt_ok = False
    except Exception as e:
        print(f"[startup] mqtt init failed: {e}", file=sys.stderr)
        app.state.mqtt_client = None
        app.state.mqtt_ok = False

    # wire mqtt publish into tracking engine if available
    def _publish(topic: str, payload: dict):
        mc = getattr(app.state, "mqtt_client", None)
        if mc and mc._client:
            import json
            mc._client.publish(topic, json.dumps(payload), qos=0)
    if getattr(app.state, "tracking_engine", None):
        app.state.tracking_engine.mqtt_publish = _publish

    # init DMX engine
    try:
        from .dmx.dmx_engine import DmxEngine
        app.state.dmx_engine = DmxEngine(tracking_engine=app.state.tracking_engine)
    except Exception as e:
        print(f"[startup] dmx engine init failed: {e}", file=sys.stderr)
        app.state.dmx_engine = None

    # DMX loop
    try:
        loop.create_task(_dmx_loop())
    except Exception:
        pass
    # broadcaster loop (websocket updates)
    try:
        loop.create_task(_broadcaster())
    except Exception as e:
        print(f"[startup] broadcaster start failed: {e}", file=sys.stderr)


async def _dmx_loop():
    while True:
        try:
            eng = getattr(app.state, "dmx_engine", None)
            if eng:
                eng.tick()
        except Exception:
            pass
        await asyncio.sleep(1.0 / 30.0)


async def _broadcaster():
    # periodically read anchor_positions and tracking positions and broadcast to connected websockets
    while True:
        await asyncio.sleep(0.2)
        try:
            from .db import connect_db
            db = connect_db()
            try:
                rows = db.execute('SELECT mac,x_cm,y_cm,z_cm,updated_at_ms FROM anchor_positions').fetchall()
            except Exception:
                rows = []
            finally:
                db.close()

            events = []
            ts = int(asyncio.get_event_loop().time() * 1000)
            for r in rows:
                events.append({'type': 'anchor_pos', 'mac': r['mac'], 'position_cm': {'x': r['x_cm'], 'y': r['y_cm'], 'z': r['z_cm']}, 'ts_ms': r['updated_at_ms'] or ts})

            te = getattr(app.state, 'tracking_engine', None)
            if te:
                for tag, payload in te.latest_position.items():
                    ev = payload.copy()
                    ev['type'] = 'tracking'
                    ev['tag_mac'] = tag
                    events.append(ev)

            if not events:
                continue

            # broadcast
            to_remove = []
            for ws in list(app.state.ws_clients):
                try:
                    await ws.send_text(json.dumps({'type': 'bulk', 'events': events}))
                except Exception:
                    to_remove.append(ws)
            for ws in to_remove:
                app.state.ws_clients.discard(ws)
        except Exception:
            await asyncio.sleep(1)


@app.websocket('/ws/live')
async def ws_live(websocket: WebSocket):
    await websocket.accept()
    app.state.ws_clients.add(websocket)
    try:
        # simple keep-alive loop
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # send ping
                try:
                    await websocket.send_text(json.dumps({'type': 'ping'}))
                except Exception:
                    break
    finally:
        app.state.ws_clients.discard(websocket)


app.include_router(api_router)


@app.get('/', response_class=HTMLResponse)
def ui_index(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})


@app.get('/ui', response_class=HTMLResponse)
@app.get('/ui/', response_class=HTMLResponse)
def ui_index_alias(request: Request):
    # serve dashboard for /ui and /ui/ to align with nav link
    return templates.TemplateResponse('index.html', {'request': request})


@app.get('/ui/{page}', response_class=HTMLResponse)
def ui_page(page: str, request: Request):
    # safe mapping for a handful of pages
    mapping = {
        'anchors': 'anchors.html',
        'tags': 'tags.html',
        'fixtures': 'fixtures.html',
        'live': 'live.html',
        'calibration': 'calibration.html',
        'settings': 'settings.html',
        'logs': 'logs.html',
        'index': 'index.html',
        'library': 'ofl_library.html',
    }
    tpl = mapping.get(page)
    if not tpl:
        return templates.TemplateResponse('index.html', {'request': request})
    from app.db import get_db_path
    ctx = {'request': request, 'db_path': get_db_path()}
    if page == 'settings' and get_persistence:
        try:
            p = get_persistence()
            settings = getattr(p, "list_settings", lambda: [])()
            ctx['settings_prefill'] = {s['key']: s['value'] for s in settings} if settings else {}
            if _load_dmx_config:
                try:
                    ctx['dmx_prefill'] = _load_dmx_config()
                except Exception:
                    ctx['dmx_prefill'] = {}
        except Exception:
            ctx['settings_prefill'] = {}
            ctx['dmx_prefill'] = {}
    return templates.TemplateResponse(tpl, ctx)


@app.get('/ui/fixtures/new', response_class=HTMLResponse)
def ui_fixture_new(request: Request):
    return templates.TemplateResponse('fixture_new.html', {'request': request})


@app.get('/ui/fixtures/{fixture_id}/edit', response_class=HTMLResponse)
def ui_fixture_edit(fixture_id: int, request: Request):
    return templates.TemplateResponse('fixture_edit.html', {'request': request, 'fixture_id': fixture_id})


@app.get('/ui/library', response_class=HTMLResponse)
def ui_library(request: Request):
    return templates.TemplateResponse('ofl_library.html', {'request': request})


@app.get('/ui/patch/{patch_id}/edit', response_class=HTMLResponse)
def ui_patch_edit(patch_id: int, request: Request):
    return templates.TemplateResponse('ofl_patch_edit.html', {'request': request, 'patch_id': patch_id})
