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

app = FastAPI()

BASE_DIR = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, 'web', 'templates'))
app.mount('/static', StaticFiles(directory=os.path.join(BASE_DIR, 'web', 'static')), name='static')


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
        mc = MQTTClientWrapper(broker_host=os.environ.get('MQTT_HOST','localhost'), broker_port=int(os.environ.get('MQTT_PORT','1883')), tracking_engine=app.state.tracking_engine)
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


async def _dmx_loop():
    while True:
        try:
            eng = getattr(app.state, "dmx_engine", None)
            if eng:
                eng.tick()
        except Exception:
            pass
        await asyncio.sleep(1.0 / 30.0)

    # start broadcaster task
    try:
        loop.create_task(_broadcaster())
    except RuntimeError:
        # if no running loop (uvicorn will provide one), ignore
        pass


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


@app.get('/ui/{page}', response_class=HTMLResponse)
def ui_page(page: str, request: Request):
    # safe mapping for a handful of pages
    allowed = ['anchors','fixtures','live','calibration','settings','logs','index']
    if page not in allowed:
        return templates.TemplateResponse('index.html', {'request': request})
    return templates.TemplateResponse(f"{page}.html", {'request': request})
