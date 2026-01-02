from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

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
