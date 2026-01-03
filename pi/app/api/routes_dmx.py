from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, validator

from app.db.persistence import get_persistence

router = APIRouter()


class AimPayload(BaseModel):
    x_cm: float
    y_cm: float
    z_cm: float
    duration_ms: int = Field(1000, ge=10, le=60000)


@router.post("/dmx/aim")
def dmx_aim(body: AimPayload, request: Request):
    eng = getattr(request.app.state, "dmx_engine", None)
    if not eng:
        raise HTTPException(status_code=503, detail="dmx engine not available")
    eng.aim({"x": body.x_cm, "y": body.y_cm, "z": body.z_cm}, body.duration_ms)
    return {"ok": True}


@router.post("/dmx/stop")
def dmx_stop(request: Request):
    eng = getattr(request.app.state, "dmx_engine", None)
    if not eng:
        raise HTTPException(status_code=503, detail="dmx engine not available")
    eng.stop_test()
    return {"ok": True}


class DmxConfig(BaseModel):
    mode: str = Field("uart", description="uart | artnet | off")
    uart_device: str | None = Field(None, description="e.g. /dev/serial0")
    artnet_target: str | None = Field(None, description="IPv4 target or broadcast")
    artnet_port: int | None = Field(None, ge=1, le=65535)
    artnet_universe: int | None = Field(None, ge=0, le=32767)

    @validator("mode")
    def _mode_lower(cls, v):
        if v is None:
            return "uart"
        return str(v).lower()


def _load_dmx_config():
    p = get_persistence()
    mode = (p.get_setting("dmx.output_mode", "uart") or "uart").lower()
    def _as_int(val, default):
        try:
            return int(val)
        except Exception:
            return default
    return {
        "mode": mode,
        "uart_device": p.get_setting("dmx.uart_device", "/dev/serial0") or "/dev/serial0",
        "artnet_target": p.get_setting("artnet.target_ip", "255.255.255.255") or "255.255.255.255",
        "artnet_port": _as_int(p.get_setting("artnet.port", 6454), 6454),
        "artnet_universe": _as_int(p.get_setting("artnet.universe", 0), 0),
    }


@router.get("/dmx/config")
def get_dmx_config():
    return {"config": _load_dmx_config()}


@router.put("/dmx/config")
def put_dmx_config(body: DmxConfig):
    p = get_persistence()
    state = p.get_setting("system.state", "SETUP")
    if state == "LIVE":
        raise HTTPException(status_code=409, detail={"code": "STATE_BLOCKED", "message": "Cannot change settings while LIVE"})

    mode = body.mode.lower()
    if mode not in ("uart", "artnet", "off"):
        raise HTTPException(status_code=400, detail={"code": "INVALID_MODE", "message": f"Unsupported mode '{mode}'"})

    p.upsert_setting("dmx.output_mode", mode)

    if mode == "uart":
        if body.uart_device:
            p.upsert_setting("dmx.uart_device", body.uart_device)
    elif mode == "artnet":
        if body.artnet_target:
            p.upsert_setting("artnet.target_ip", body.artnet_target)
        if body.artnet_port is not None:
            p.upsert_setting("artnet.port", str(body.artnet_port))
        if body.artnet_universe is not None:
            p.upsert_setting("artnet.universe", str(body.artnet_universe))

    return {"ok": True, "config": _load_dmx_config()}
