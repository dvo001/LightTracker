import json
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional

from app.dmx.ssl2_import import parse_ssl2_fixture

from app.db.persistence import get_persistence


def _assert_not_live(p):
    # guard destructive/modify actions while system is LIVE
    state = p.get_setting('system.state', 'SETUP')
    if state == 'LIVE':
        raise HTTPException(status_code=409, detail={"code": "STATE_BLOCKED", "message": "Operation not allowed while system is LIVE"})


router = APIRouter()


class FixtureIn(BaseModel):
    name: str
    universe: int = Field(1, ge=1)
    dmx_base_addr: int = Field(..., ge=1, le=512)
    profile_key: str
    pos_x_cm: Optional[int] = 0
    pos_y_cm: Optional[int] = 0
    pos_z_cm: Optional[int] = 0


@router.get("/fixture-profiles")
def list_profiles():
    p = get_persistence()
    return {"profiles": p.list_fixture_profiles()}

@router.post("/fixture-profiles/import-ssl2")
async def import_fixture_profile_ssl2(file: UploadFile = File(...), profile_key: Optional[str] = Form(None)):
    p = get_persistence()
    _assert_not_live(p)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    try:
        derived_key, profile = parse_ssl2_fixture(data, filename=file.filename or "")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"could not parse ssl2: {e}")

    key = profile_key or derived_key
    try:
        p.upsert_fixture_profile(key, json.dumps(profile))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to store profile: {e}")
    return {"ok": True, "profile_key": key, "profile": profile}


@router.get("/fixtures")
def list_fixtures():
    p = get_persistence()
    return {"fixtures": p.list_fixtures()}


@router.post("/fixtures")
def create_fixture(body: FixtureIn):
    p = get_persistence()
    _assert_not_live(p)
    # basic validation: ensure fits in 512 using profile channels if available
    profiles = {pr['profile_key']: pr for pr in p.list_fixture_profiles()}
    profile = profiles.get(body.profile_key)
    channel_count = 4
    if profile:
        import json
        try:
            pj = json.loads(profile['profile_json'])
            channel_count = pj.get('channels', channel_count)
        except Exception:
            pass
    if body.dmx_base_addr + channel_count - 1 > 512:
        raise HTTPException(status_code=400, detail="DMX channels exceed universe size")
    fid = p.create_fixture(body.dict())
    return {"id": fid}


@router.get("/fixtures/{fid}")
def get_fixture(fid: int):
    p = get_persistence()
    f = p.get_fixture(fid)
    if not f:
        raise HTTPException(status_code=404)
    return f


@router.put("/fixtures/{fid}")
def put_fixture(fid: int, body: dict):
    p = get_persistence()
    _assert_not_live(p)
    ok = p.update_fixture(fid, body)
    if not ok:
        raise HTTPException(status_code=404)
    return {"ok": True}


@router.delete("/fixtures/{fid}")
def delete_fixture(fid: int):
    p = get_persistence()
    _assert_not_live(p)
    ok = p.delete_fixture(fid)
    if not ok:
        raise HTTPException(status_code=404)
    return {"deleted": True}


@router.post("/fixtures/{fid}/enable")
def enable_fixture(fid: int):
    p = get_persistence()
    _assert_not_live(p)
    ok = p.update_fixture(fid, {"enabled": 1})
    if not ok:
        raise HTTPException(status_code=404)
    return {"ok": True}


@router.post("/fixtures/{fid}/disable")
def disable_fixture(fid: int):
    p = get_persistence()
    _assert_not_live(p)
    ok = p.update_fixture(fid, {"enabled": 0})
    if not ok:
        raise HTTPException(status_code=404)
    return {"ok": True}
# /fixtures routes
