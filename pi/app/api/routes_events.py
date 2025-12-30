from fastapi import APIRouter
import sqlite3

from app.db.database import get_db_path


router = APIRouter()


@router.get("/events")
def list_events(limit: int = 100):
    db = get_db_path()
    conn = sqlite3.connect(db)
    cur = conn.execute("SELECT id,ts_ms,level,source,event_type,ref,details_json FROM event_log ORDER BY ts_ms DESC LIMIT ?", (limit,))
    rows = [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]
    conn.close()
    return {"events": rows}
# /events routes
