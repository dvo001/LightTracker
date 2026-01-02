from fastapi import APIRouter, Request, HTTPException
router = APIRouter()


@router.get('/tracking/tags')
def list_tracking_tags(request: Request):
    te = getattr(request.app.state, 'tracking_engine', None)
    if not te:
        return {'tags': []}
    out = []
    now = int(__import__('time').time()*1000)
    for tag, payload in te.latest_position.items():
        age = now - payload.get('ts_ms', now)
        out.append({'tag_mac': tag, 'state': payload.get('state'), 'age_ms': age, 'anchors_used': payload.get('anchors_used'), 'quality': payload.get('quality'), 'last_ts_ms': payload.get('ts_ms')})
    return {'tags': out}


@router.get('/tracking/position/{tag_mac}')
def get_tracking_position(tag_mac: str, request: Request):
    te = getattr(request.app.state, 'tracking_engine', None)
    if not te:
        raise HTTPException(status_code=404, detail='tracking engine not available')
    p = te.latest_position.get(tag_mac)
    if not p:
        raise HTTPException(status_code=404, detail='not found')
    return p
