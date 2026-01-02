from fastapi import APIRouter
from app.db.persistence import get_persistence


router = APIRouter()


@router.get("/events")
def list_events(limit: int = 200):
    p = get_persistence()
    return {"events": p.list_events(limit=limit)}
