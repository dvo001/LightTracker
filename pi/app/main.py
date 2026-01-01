from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import threading
import asyncio
import json

from .db.migrations.runner import run_migrations
from .api import router as api_router

app = FastAPI()

BASE_DIR = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, 'web', 'templates'))
app.mount('/static', StaticFiles(directory=os.path.join(BASE_DIR, 'web', 'static')), name='static')


@app.on_event('startup')
def startup():
    # Run migrations in a separate thread to avoid blocking startup in dev
    def _run():
        try:
            run_migrations()
        except Exception:
            pass
    t = threading.Thread(target=_run)
    t.daemon = True
    t.start()

    # initialize state for websocket clients and calibration
    app.state.ws_clients = set()
    app.state.active_calibration = None

    # start broadcaster task
    loop = asyncio.get_event_loop()
    try:
        loop.create_task(_broadcaster())
    except RuntimeError:
        # if no running loop (uvicorn will provide one), ignore
        pass


async def _broadcaster():
    # periodically read anchor_positions and broadcast to connected websockets
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
