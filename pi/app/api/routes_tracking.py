from fastapi import APIRouter, HTTPException
from typing import List

from app.core.tracking_engine import TrackingEngine
from fastapi import APIRouter

router = APIRouter()


@router.get("/tracking/tags")
def list_tags():
    # read from running engine
    engine = getattr(main_app.state, 'tracking_engine', None)
    if not engine:
        return {"tags": []}
    items = []
    for tag, payload in engine.latest_position.items():
        items.append({"tag_mac": tag, "state": payload.get('state')})
    return {"tags": items}


@router.get("/tracking/position/{tag_mac}")
def get_position(tag_mac: str):
    engine = getattr(main_app.state, 'tracking_engine', None)
    if not engine:
        raise HTTPException(status_code=404, detail="tracking not running")
    payload = engine.latest_position.get(tag_mac)
    if not payload:
        raise HTTPException(status_code=404, detail="no position for tag")
    return payload
# /tracking routes
