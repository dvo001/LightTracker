from fastapi import APIRouter
from ..db import connect_db
import time

router = APIRouter()


@router.get('/state')
def get_state():
    # Minimal system state for UI; extend as needed
    db = connect_db()
    try:
        cur = db.execute('SELECT COUNT(1) as cnt FROM fixtures')
        fixtures_cnt = cur.fetchone()['cnt'] if cur else 0
    except Exception:
        fixtures_cnt = 0
    finally:
        db.close()

    return {
        'system_state': 'SETUP',
        'mqtt_ok': False,
        'anchors_online': 0,
        'fixtures_count': fixtures_cnt,
        'ts_ms': int(time.time() * 1000)
    }
