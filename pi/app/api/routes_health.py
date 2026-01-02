from fastapi import APIRouter, Request
from ..db import connect_db
import time

router = APIRouter()


@router.get('/health')
def health(request: Request):
    # Check DB
    db_ok = False
    migrations = None
    try:
        db = connect_db()
        try:
            cur = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'")
            row = cur.fetchone()
            migrations = True if row else False
            db.execute('SELECT 1')
            db_ok = True
        finally:
            db.close()
    except Exception:
        db_ok = False

    # mqtt status may be stored on app.state.mqtt_ok by startup routines
    mqtt_ok = getattr(request.app.state, 'mqtt_ok', None)

    return {
        'ts_ms': int(time.time() * 1000),
        'db_ok': db_ok,
        'migrations_table_present': migrations,
        'mqtt_ok': mqtt_ok
    }
