import hashlib
import json
import time
import io
import zipfile
from typing import Optional, Dict, Any, Tuple

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from pydantic import BaseModel, Field

from app.db.persistence import get_persistence
from app.db import connect_db

router = APIRouter()


def _normalize_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _load_ofl_json(raw: bytes, filename: str = "") -> Tuple[dict, Optional[str], Optional[str]]:
    """Accept plain JSON or a zip containing JSON. Returns (obj, mfr_inferred, model_inferred)."""
    data = raw
    inferred_mfr = None
    inferred_model = None
    pick_name = filename or ""
    try:
        if zipfile.is_zipfile(io.BytesIO(raw)):
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                names = z.namelist()
                pick = None
                for n in names:
                    if n.lower().endswith(".json"):
                        pick = n
                        break
                pick = pick or (names[0] if names else None)
                if not pick:
                    raise ValueError("zip is empty")
                data = z.read(pick)
                pick_name = pick
                parts = pick.replace("\\", "/").split("/")
                if len(parts) >= 2:
                    inferred_mfr = parts[-2] or None
                if parts:
                    inferred_model = parts[-1].rsplit(".", 1)[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid OFL archive: {e}")

    try:
        obj = json.loads(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    if not inferred_model and pick_name:
        inferred_model = pick_name.rsplit("/", 1)[-1].rsplit(".", 1)[0] if "/" in pick_name or "." in pick_name else None
    return obj, inferred_mfr, inferred_model


def _extract_modes(fixture_obj: dict):
    modes = fixture_obj.get("modes") or []
    out = []
    for m in modes:
        if isinstance(m, dict):
            name = m.get("name") or m.get("modeName") or "unnamed"
            channels = m.get("channels") or []
            out.append({"name": name, "channels": len(channels), "raw": m})
    return out


def _find_channel_indexes(fixture: dict, mode_name: str):
    modes = fixture.get("modes") or []
    target_mode = None
    for m in modes:
        if not isinstance(m, dict):
            continue
        if (m.get("name") or m.get("modeName")) == mode_name:
            target_mode = m
            break
    if not target_mode:
        return None, None, []

    chan_list = target_mode.get("channels") or []
    available = fixture.get("availableChannels") or {}
    dimmer_idx = None
    shutter_idx = None
    color_idx = None
    rgb_idxs = []
    for idx, ch in enumerate(chan_list, start=0):
        key = ch if isinstance(ch, str) else ch.get("name") if isinstance(ch, dict) else None
        details = available.get(key) if isinstance(available, dict) else {}
        name = key or details.get("name") if isinstance(details, dict) else ""
        lower = (name or "").lower()
        if dimmer_idx is None and "dim" in lower:
            dimmer_idx = idx
        if shutter_idx is None and ("shutter" in lower or "strobe" in lower):
            shutter_idx = idx
        if color_idx is None and ("color" in lower or "colour" in lower):
            color_idx = idx
        if "red" in lower or "green" in lower or "blue" in lower or "white" in lower:
            rgb_idxs.append(idx)
        caps = details.get("capabilities") if isinstance(details, dict) else None
        if caps and isinstance(caps, list):
            for cap in caps:
                typ = (cap.get("type") or "").lower()
                if dimmer_idx is None and "intensity" in typ:
                    dimmer_idx = idx
                if shutter_idx is None and ("shutter" in typ or "strobe" in typ):
                    shutter_idx = idx
                if color_idx is None and ("color" in typ or "colour" in typ):
                    color_idx = idx
                if "red" in typ or "green" in typ or "blue" in typ or "white" in typ:
                    rgb_idxs.append(idx)
    return dimmer_idx, shutter_idx, color_idx, rgb_idxs, chan_list


def _assert_not_live():
    p = get_persistence()
    state = p.get_setting("system.state", "SETUP")
    if state == "LIVE":
        raise HTTPException(status_code=409, detail={"code": "STATE_BLOCKED", "message": "Operation not allowed while system is LIVE"})


@router.post("/ofl/fixtures/import")
async def import_ofl_fixture(file: UploadFile = File(...), manufacturer: Optional[str] = Form(None), model: Optional[str] = Form(None)):
    _assert_not_live()
    raw = await file.read()
    obj, inferred_mfr, inferred_model = _load_ofl_json(raw, filename=file.filename or "")
    if not isinstance(obj, dict):
        raise HTTPException(status_code=400, detail="OFL JSON must be an object")
    modes = obj.get("modes")
    if not modes or not isinstance(modes, list):
        raise HTTPException(status_code=400, detail="OFL JSON missing modes[]")

    ofl_schema = obj.get("$schema")
    mfr = manufacturer or obj.get("manufacturer") or obj.get("manufacturerName") or obj.get("manufacturerKey") or inferred_mfr
    mdl = model or obj.get("name") or obj.get("model") or obj.get("key") or inferred_model
    if not mfr or not mdl:
        raise HTTPException(status_code=400, detail="manufacturer/model required (either in JSON or form fields)")

    norm = _normalize_json(obj)
    content_hash = hashlib.sha256(norm.encode("utf-8")).hexdigest()

    p = get_persistence()
    existing = p.find_ofl_fixture_by_hash(content_hash)
    fid = None
    duplicate = False
    if existing:
        fid = existing["id"]
        duplicate = True
    else:
        fid = p.upsert_ofl_fixture(mfr, mdl, ofl_schema, norm, content_hash)
    return {"fixture_id": fid, "duplicate": duplicate, "manufacturer": mfr, "model": mdl}


@router.get("/ofl/fixtures")
def list_ofl_fixtures(q: Optional[str] = None):
    p = get_persistence()
    rows = p.search_ofl_fixtures(q)
    fixtures = []
    for r in rows:
        try:
            obj = json.loads(r["ofl_json"])
        except Exception:
            obj = {}
        modes = _extract_modes(obj)
        fixtures.append({
            "id": r["id"],
            "manufacturer": r["manufacturer"],
            "model": r["model"],
            "modes": [{"name": m["name"], "channels": m["channels"]} for m in modes],
        })
    return {"fixtures": fixtures}


@router.get("/ofl/fixtures/{fid}")
def get_ofl_fixture(fid: int):
    p = get_persistence()
    row = p.get_ofl_fixture(fid)
    if not row:
        raise HTTPException(status_code=404)
    try:
        obj = json.loads(row["ofl_json"])
    except Exception:
        obj = {}
    return {
        "id": row["id"],
        "manufacturer": row["manufacturer"],
        "model": row["model"],
        "ofl_schema": row["ofl_schema"],
        "ofl_json": obj,
    }


class PatchIn(BaseModel):
    fixture_id: int
    name: str
    mode_name: str
    universe: int = Field(0, ge=0)
    dmx_address: int = Field(..., ge=1, le=512)
    overrides_json: Optional[Dict[str, Any]] = None


@router.post("/ofl/patched-fixtures")
def create_patched_fixture(body: PatchIn):
    _assert_not_live()
    p = get_persistence()
    fx = p.get_ofl_fixture(body.fixture_id)
    if not fx:
        raise HTTPException(status_code=404, detail="fixture not found")
    try:
        obj = json.loads(fx["ofl_json"])
    except Exception:
        obj = {}
    modes = _extract_modes(obj)
    target_mode = next((m for m in modes if m["name"] == body.mode_name), None)
    if not target_mode:
        raise HTTPException(status_code=400, detail="mode not found in fixture")
    if body.dmx_address + target_mode["channels"] - 1 > 512:
        raise HTTPException(status_code=400, detail="DMX address out of range for selected mode")
    overrides_str = json.dumps(body.overrides_json) if body.overrides_json is not None else None
    pid = p.create_patched_fixture(body.fixture_id, body.name, body.mode_name, body.universe, body.dmx_address, overrides_str)
    return {"id": pid}


@router.get("/ofl/patched-fixtures")
def list_patched_fixtures():
    p = get_persistence()
    rows = p.list_patched_fixtures()
    fixtures = {fx["id"]: fx for fx in p.search_ofl_fixtures()}
    out = []
    for r in rows:
        fx = fixtures.get(r["fixture_id"])
        out.append({
            "id": r["id"],
            "name": r["name"],
            "mode_name": r["mode_name"],
            "universe": r["universe"],
            "dmx_address": r["dmx_address"],
            "fixture": {"id": r["fixture_id"], "manufacturer": fx["manufacturer"] if fx else None, "model": fx["model"] if fx else None},
        })
    return {"patched_fixtures": out}


@router.get("/ofl/patched-fixtures/{pid}")
def get_patched_fixture(pid: int):
    p = get_persistence()
    row = p.get_patched_fixture(pid)
    if not row:
        raise HTTPException(status_code=404)
    fx = p.get_ofl_fixture(row["fixture_id"])
    fx_obj = {}
    if fx:
        try:
            fx_obj = json.loads(fx["ofl_json"])
        except Exception:
            fx_obj = {}
    return {
        "patch": row,
        "fixture": fx,
        "fixture_json": fx_obj,
    }


@router.put("/ofl/patched-fixtures/{pid}")
def update_patched_fixture(pid: int, body: PatchIn):
    _assert_not_live()
    p = get_persistence()
    row = p.get_patched_fixture(pid)
    if not row:
        raise HTTPException(status_code=404, detail="patched fixture not found")
    fx = p.get_ofl_fixture(body.fixture_id)
    if not fx:
        raise HTTPException(status_code=404, detail="fixture not found")
    try:
        obj = json.loads(fx["ofl_json"])
    except Exception:
        obj = {}
    modes = _extract_modes(obj)
    target_mode = next((m for m in modes if m["name"] == body.mode_name), None)
    if not target_mode:
        raise HTTPException(status_code=400, detail="mode not found in fixture")
    if body.dmx_address + target_mode["channels"] - 1 > 512:
        raise HTTPException(status_code=400, detail="DMX address out of range for selected mode")
    overrides_str = json.dumps(body.overrides_json) if body.overrides_json is not None else None
    conn = connect_db()
    try:
        ts = int(time.time() * 1000)
        cur = conn.execute(
            """UPDATE patched_fixtures SET fixture_id=?, name=?, mode_name=?, universe=?, dmx_address=?, overrides_json=?, updated_at_ms=? WHERE id=?""",
            (body.fixture_id, body.name, body.mode_name, body.universe, body.dmx_address, overrides_str, ts, pid),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="not updated")
    finally:
        conn.close()
    return {"ok": True}


def _build_test_frame(fixture_obj: dict, mode_name: str, base_addr: int, on: bool):
    dimmer_idx, shutter_idx, color_idx, rgb_idxs, chan_list = _find_channel_indexes(fixture_obj, mode_name)
    channel_values = {}
    warnings = []
    if dimmer_idx is not None:
        channel_values[base_addr + dimmer_idx] = 255 if on else 0
    else:
        warnings.append("no dimmer channel found")
    if shutter_idx is not None:
        channel_values[base_addr + shutter_idx] = 255 if on else 0
    if dimmer_idx is None and color_idx is not None:
        channel_values[base_addr + color_idx] = 255 if on else 0
        warnings.append("using color channel as intensity fallback")
    if dimmer_idx is None and rgb_idxs:
        for idx in rgb_idxs:
            channel_values[base_addr + idx] = 255 if on else 0
        warnings.append("using rgb channels as intensity fallback")
    if not channel_values and chan_list:
        channel_values[base_addr] = 255 if on else 0
        warnings.append("fallback: set first channel to 255")
    if not channel_values:
        warnings.append("no channels to set")
    return channel_values, warnings


def _send_test_frame(request: Request, universe: int, channel_values: dict):
    eng = getattr(request.app.state, "dmx_engine", None)
    if not eng:
        raise HTTPException(status_code=503, detail="dmx engine not available")
    eng.send_custom_frame(universe, channel_values)


@router.post("/ofl/patched-fixtures/{pid}/test/light-on")
def patched_fixture_light_on(pid: int, request: Request):
    p = get_persistence()
    row = p.get_patched_fixture(pid)
    if not row:
        raise HTTPException(status_code=404, detail="patched fixture not found")
    fx = p.get_ofl_fixture(row["fixture_id"])
    if not fx:
        raise HTTPException(status_code=404, detail="fixture missing")
    try:
        obj = json.loads(fx["ofl_json"])
    except Exception:
        obj = {}
    channel_values, warnings = _build_test_frame(obj, row["mode_name"], row["dmx_address"], True)
    if not channel_values:
        raise HTTPException(status_code=400, detail={"message": "no channels inferred", "warnings": warnings})
    _send_test_frame(request, row["universe"], channel_values)
    writes = [{"channel": ch, "value": val} for ch, val in sorted(channel_values.items())]
    return {"patched_fixture_id": pid, "writes": writes, "warnings": warnings}


@router.post("/ofl/patched-fixtures/{pid}/test/light-off")
def patched_fixture_light_off(pid: int, request: Request):
    p = get_persistence()
    row = p.get_patched_fixture(pid)
    if not row:
        raise HTTPException(status_code=404, detail="patched fixture not found")
    fx = p.get_ofl_fixture(row["fixture_id"])
    if not fx:
        raise HTTPException(status_code=404, detail="fixture missing")
    try:
        obj = json.loads(fx["ofl_json"])
    except Exception:
        obj = {}
    channel_values, warnings = _build_test_frame(obj, row["mode_name"], row["dmx_address"], False)
    if not channel_values:
        raise HTTPException(status_code=400, detail={"message": "no channels inferred", "warnings": warnings})
    _send_test_frame(request, row["universe"], channel_values)
    writes = [{"channel": ch, "value": val} for ch, val in sorted(channel_values.items())]
    return {"patched_fixture_id": pid, "writes": writes, "warnings": warnings}
