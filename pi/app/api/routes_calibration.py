from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Dict, Optional
from ..db import connect_db
import math
import time
import asyncio
import json

from app.core.calibration_manager import CalibrationManager
from app.core.state_manager import StateManager
from app.core.anchor_positions import load_anchor_positions, load_anchor_offsets, ensure_anchor_offsets_table
from app.core.trilateration import solve_3d
from app.db.persistence import get_persistence

router = APIRouter()


def ensure_calibration_table(db):
    db.execute('''CREATE TABLE IF NOT EXISTS calibration_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tag_mac TEXT,
        started_at_ms INTEGER,
        ended_at_ms INTEGER,
        result TEXT,
        invalidated_at_ms INTEGER,
        params_json TEXT,
        summary_json TEXT,
        status TEXT,
        committed_at_ms INTEGER,
        discarded_at_ms INTEGER
    )''')
    db.commit()


class CalStart(BaseModel):
    tag_mac: str
    duration_ms: int = Field(6000, ge=100, le=60000)


class CalPointPos(BaseModel):
    x: float
    y: float
    z: float


class CalPoint(BaseModel):
    tag_mac: str
    duration_ms: int = Field(6000, ge=100, le=60000)
    point_id: str = Field(..., min_length=1, max_length=32)
    position_cm: CalPointPos
    session_id: Optional[str] = None
    grid_cm: Optional[int] = None
    label: Optional[str] = None


class CalSolve(BaseModel):
    tag_mac: str
    apply: bool = True
    min_points: int = Field(4, ge=4, le=10)


@router.get('/calibration/status')
def calibration_status(request: Request):
    cm = getattr(request.app.state, 'calibration_manager', None)
    if cm and cm.active:
        return cm.status()
    # no active run -> return last finished run (if any) for commit/discard
    db = connect_db()
    try:
        ensure_calibration_table(db)
        row = db.execute(
            "SELECT id, tag_mac, started_at_ms, ended_at_ms, result, status "
            "FROM calibration_runs WHERE status='finished' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row:
            r = dict(row)
            return {
                "running": False,
                "run_id": r.get("id"),
                "tag_mac": r.get("tag_mac"),
                "started_at_ms": r.get("started_at_ms"),
                "ended_at_ms": r.get("ended_at_ms"),
                "result": r.get("result"),
                "status": r.get("status"),
                "progress": {},
            }
    finally:
        db.close()
    return {'running': False, 'run_id': None, 'tag_mac': None, 'started_at_ms': None, 'progress': {}}


@router.post('/calibration/start')
async def calibration_start(payload: CalStart, request: Request):
    sm = StateManager()
    if sm.get_state() == "LIVE":
        raise HTTPException(status_code=409, detail={'code': 'STATE_BLOCKED', 'message': 'Cannot start calibration while LIVE'})
    cm = getattr(request.app.state, 'calibration_manager', None)
    if not cm:
        # init on demand
        from app.core.tracking_engine import TrackingEngine
        te = getattr(request.app.state, 'tracking_engine', TrackingEngine())
        cm = CalibrationManager(te.range_cache)
        request.app.state.calibration_manager = cm
    try:
        run_id = cm.start(payload.tag_mac, payload.duration_ms)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    # schedule ticking loop
    loop = asyncio.get_event_loop()
    loop.create_task(_cal_tick_loop(cm))
    sm.set_state("CALIBRATION")
    return {'ok': True, 'run_id': run_id}


async def _cal_tick_loop(cm: CalibrationManager):
    while cm.active:
        cm.tick()
        await asyncio.sleep(0.1)
    # done -> set state back to SETUP
    sm = StateManager()
    sm.set_state("SETUP")


async def _collect_range_samples(range_cache, tag_mac: str, duration_ms: int, sample_interval_ms: int = 50):
    end_ts = time.time() + (duration_ms / 1000.0)
    samples = []
    last_ts_by_anchor: Dict[str, int] = {}
    while time.time() < end_ts:
        snap = range_cache.snapshot(tag_mac)
        for s in snap:
            prev_ts = last_ts_by_anchor.get(s.anchor_mac)
            if prev_ts is None or s.ts_ms > prev_ts:
                samples.append(s)
                last_ts_by_anchor[s.anchor_mac] = s.ts_ms
        await asyncio.sleep(sample_interval_ms / 1000.0)
    return samples


def _normalize_mac(mac: str) -> str:
    if not mac:
        return ""
    import re
    return re.sub(r"[^0-9A-Fa-f]", "", mac).upper()


def _dist_cm(a, b) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _fit_linear(pairs):
    n = len(pairs)
    if n <= 0:
        return 1.0, 0.0, 0.0
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    if n == 1:
        scale = 1.0
        offset = ys[0] - xs[0]
    else:
        sx = sum(xs)
        sy = sum(ys)
        sxx = sum(x * x for x in xs)
        sxy = sum(x * y for x, y in pairs)
        denom = (n * sxx - sx * sx)
        if abs(denom) < 1e-9:
            scale = 1.0
            offset = sum((y - x) for x, y in pairs) / n
        else:
            scale = (n * sxy - sx * sy) / denom
            offset = (sy - scale * sx) / n
    rms = 0.0
    for x, y in pairs:
        err = (scale * x + offset) - y
        rms += err * err
    rms = math.sqrt(rms / n) if n else 0.0
    return scale, offset, rms


@router.post('/calibration/point')
async def calibration_point(payload: CalPoint, request: Request):
    sm = StateManager()
    if sm.get_state() == "LIVE":
        raise HTTPException(status_code=409, detail={'code': 'STATE_BLOCKED', 'message': 'Cannot start calibration while LIVE'})

    cm = getattr(request.app.state, 'calibration_manager', None)
    if cm and cm.active:
        raise HTTPException(status_code=409, detail="calibration already running")

    from app.core.tracking_engine import TrackingEngine
    te = getattr(request.app.state, 'tracking_engine', TrackingEngine())
    sm.set_state("CALIBRATION")
    start_ts = int(time.time() * 1000)
    try:
        samples = await _collect_range_samples(te.range_cache, payload.tag_mac, payload.duration_ms)
    finally:
        sm.set_state("SETUP")
    end_ts = int(time.time() * 1000)

    per_anchor = {}
    for s in samples:
        per_anchor.setdefault(s.anchor_mac, []).append(s.d_m)
    per_anchor_stats = {}
    for anchor, vals in per_anchor.items():
        vals_sorted = sorted(vals)
        median = vals_sorted[len(vals_sorted) // 2]
        avg = sum(vals) / len(vals)
        per_anchor_stats[anchor] = {
            "median_d_m": median,
            "mean_d_m": avg,
            "min_d_m": vals_sorted[0],
            "max_d_m": vals_sorted[-1],
            "count": len(vals),
        }

    anchors_used = sorted(per_anchor_stats.keys())
    result = "OK" if len(anchors_used) >= 2 else "FAILED"
    session_id = payload.session_id or f"sess_{int(time.time() * 1000)}"
    params = {
        "v": 2,
        "type": "venue_point",
        "session_id": session_id,
        "point_id": payload.point_id,
        "position_cm": payload.position_cm.dict(),
        "grid_cm": payload.grid_cm,
        "label": payload.label,
        "duration_ms": payload.duration_ms,
    }
    summary = {
        "samples": len(samples),
        "anchors_used": anchors_used,
        "result": result,
        "per_anchor": per_anchor_stats,
    }

    db = connect_db()
    try:
        ensure_calibration_table(db)
        cur = db.execute(
            "INSERT INTO calibration_runs(tag_mac, started_at_ms, ended_at_ms, result, params_json, summary_json, status) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                payload.tag_mac,
                start_ts,
                end_ts,
                result,
                json.dumps(params),
                json.dumps(summary),
                "finished",
            ),
        )
        db.commit()
        run_id = cur.lastrowid
    finally:
        db.close()

    return {
        "ok": True,
        "run_id": run_id,
        "session_id": session_id,
        "params": params,
        "summary": summary,
    }


@router.post('/calibration/solve')
def calibration_solve(payload: CalSolve, request: Request):
    sm = StateManager()
    if sm.get_state() == "LIVE":
        raise HTTPException(status_code=409, detail={'code': 'STATE_BLOCKED', 'message': 'Cannot solve calibration while LIVE'})

    tag_mac = (payload.tag_mac or "").strip()
    if not tag_mac:
        raise HTTPException(status_code=400, detail="tag_mac required")

    db = connect_db()
    try:
        ensure_calibration_table(db)
        ensure_anchor_offsets_table(db)
        base_positions = load_anchor_positions(db, with_offsets=False)
        offsets = load_anchor_offsets(db)
        current_positions = {
            mac: (pos[0] + offsets.get(mac, (0.0, 0.0, 0.0))[0],
                  pos[1] + offsets.get(mac, (0.0, 0.0, 0.0))[1],
                  pos[2] + offsets.get(mac, (0.0, 0.0, 0.0))[2])
            for mac, pos in base_positions.items()
        }
        rows = db.execute(
            "SELECT id, started_at_ms, params_json, summary_json "
            "FROM calibration_runs WHERE tag_mac=? AND status='finished' "
            "ORDER BY started_at_ms DESC",
            (tag_mac,),
        ).fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="no calibration runs for tag_mac")

        points = {}
        for r in rows:
            try:
                params = json.loads(r["params_json"] or "{}")
            except Exception:
                continue
            if params.get("type") != "venue_point":
                continue
            point_id = params.get("point_id")
            pos = params.get("position_cm")
            if not point_id or not isinstance(pos, dict):
                continue
            if point_id in points:
                continue
            try:
                summary = json.loads(r["summary_json"] or "{}")
            except Exception:
                summary = {}
            points[point_id] = {
                "run_id": r["id"],
                "started_at_ms": r["started_at_ms"],
                "position_cm": {"x": float(pos.get("x", 0.0)), "y": float(pos.get("y", 0.0)), "z": float(pos.get("z", 0.0))},
                "summary": summary,
            }
            if len(points) >= 5:
                break

        if len(points) < payload.min_points:
            raise HTTPException(status_code=400, detail=f"need at least {payload.min_points} points, got {len(points)}")

        point_positions = {pid: (p["position_cm"]["x"], p["position_cm"]["y"], p["position_cm"]["z"]) for pid, p in points.items()}

        anchor_samples = {}
        for point_id, info in points.items():
            pos = info["position_cm"]
            summary = info.get("summary") or {}
            per_anchor = summary.get("per_anchor") or {}
            for anchor_mac, stats in per_anchor.items():
                meas_m = stats.get("median_d_m")
                if meas_m is None:
                    meas_m = stats.get("mean_d_m")
                if meas_m is None:
                    continue
                anchor_samples.setdefault(anchor_mac, []).append({
                    "point_id": point_id,
                    "pos_cm": (pos["x"], pos["y"], pos["z"]),
                    "meas_cm": float(meas_m) * 100.0,
                })

        range_corrections = {}
        for anchor_mac, samples in anchor_samples.items():
            cur_pos = current_positions.get(anchor_mac)
            if not cur_pos:
                continue
            pairs = []
            points_used = []
            for s in samples:
                true_cm = _dist_cm(cur_pos, s["pos_cm"])
                pairs.append((s["meas_cm"], true_cm))
                points_used.append(s["point_id"])
            if len(pairs) < 2:
                continue
            scale, offset_cm, rms_cm = _fit_linear(pairs)
            if scale <= 0.0:
                scale = 1.0
            range_corrections[anchor_mac] = {
                "range_scale": scale,
                "range_offset_cm": offset_cm,
                "rms_cm": rms_cm,
                "points_used": sorted(set(points_used)),
            }

        anchor_offsets = {}
        for anchor_mac, samples in anchor_samples.items():
            base_pos = base_positions.get(anchor_mac)
            if not base_pos:
                continue
            corr = range_corrections.get(anchor_mac)
            if not corr:
                continue
            dists = {}
            for s in samples:
                if s["point_id"] not in point_positions:
                    continue
                d_corr_cm = corr["range_scale"] * s["meas_cm"] + corr["range_offset_cm"]
                if d_corr_cm <= 0:
                    continue
                dists[s["point_id"]] = d_corr_cm
            if len(dists) < payload.min_points:
                continue
            initial = current_positions.get(anchor_mac, base_pos)
            res = solve_3d(point_positions, dists, initial_pos_cm=initial)
            if res.pos_cm is None:
                continue
            dx = res.pos_cm[0] - base_pos[0]
            dy = res.pos_cm[1] - base_pos[1]
            dz = res.pos_cm[2] - base_pos[2]
            anchor_offsets[anchor_mac] = {
                "offset_cm": {"x": dx, "y": dy, "z": dz},
                "position_cm": {"x": res.pos_cm[0], "y": res.pos_cm[1], "z": res.pos_cm[2]},
                "resid_m": res.resid_m,
                "points_used": sorted(dists.keys()),
            }

        applied = {"range_settings": 0, "anchor_offsets": 0, "mqtt_published": 0}
        if payload.apply:
            ts = int(time.time() * 1000)
            p = get_persistence()
            for anchor_mac, corr in range_corrections.items():
                mac_norm = _normalize_mac(anchor_mac)
                if not mac_norm:
                    continue
                try:
                    p.upsert_device_setting(mac_norm, "range_scale", str(corr["range_scale"]))
                    p.upsert_device_setting(mac_norm, "range_offset_cm", str(corr["range_offset_cm"]))
                    applied["range_settings"] += 1
                except Exception:
                    pass

            for anchor_mac, info in anchor_offsets.items():
                off = info["offset_cm"]
                try:
                    db.execute(
                        "INSERT OR REPLACE INTO anchor_position_offsets(mac, dx_cm, dy_cm, dz_cm, updated_at_ms, tag_mac) "
                        "VALUES (?,?,?,?,?,?)",
                        (anchor_mac, off["x"], off["y"], off["z"], ts, tag_mac),
                    )
                    applied["anchor_offsets"] += 1
                except Exception:
                    pass
            db.commit()

            mc = getattr(request.app.state, "mqtt_client", None)
            client = getattr(mc, "_client", None) if mc else None
            if client:
                for anchor_mac, corr in range_corrections.items():
                    mac_norm = _normalize_mac(anchor_mac)
                    if not mac_norm:
                        continue
                    payload_cmd = {
                        "type": "cmd",
                        "cmd": "apply_settings",
                        "cmd_id": f"cal_{ts}_{mac_norm[-4:]}",
                        "settings": {
                            "range_scale": corr["range_scale"],
                            "range_offset_cm": corr["range_offset_cm"],
                        },
                    }
                    client.publish(f"dev/{mac_norm}/cmd", json.dumps(payload_cmd), qos=1)
                    applied["mqtt_published"] += 1

    finally:
        db.close()

    return {
        "ok": True,
        "tag_mac": tag_mac,
        "points_used": {k: v["position_cm"] for k, v in points.items()},
        "range_corrections": range_corrections,
        "anchor_offsets": anchor_offsets,
        "applied": applied,
    }


@router.post('/calibration/abort')
def calibration_abort(request: Request):
    cm = getattr(request.app.state, 'calibration_manager', None)
    if not cm or not cm.active:
        return {'ok': False, 'error': 'no active run'}
    cm.abort()
    StateManager().set_state("SETUP")
    return {'ok': True, 'run_id': None}


@router.post('/calibration/commit/{run_id}')
def calibration_commit(run_id: int):
    db = connect_db()
    try:
        db.execute('UPDATE calibration_runs SET status=?, committed_at_ms=? WHERE id=?', ('committed', int(time.time()*1000), run_id))
        db.commit()
    finally:
        db.close()
    return {'ok': True, 'run_id': run_id}


@router.post('/calibration/discard/{run_id}')
def calibration_discard(run_id: int):
    db = connect_db()
    try:
        db.execute('UPDATE calibration_runs SET status=?, discarded_at_ms=? WHERE id=?', ('discarded', int(time.time()*1000), run_id))
        db.commit()
    finally:
        db.close()
    return {'ok': True, 'run_id': run_id}


@router.get('/calibration/runs')
def list_runs():
    db = connect_db()
    try:
        ensure_calibration_table(db)
        rows = db.execute('SELECT * FROM calibration_runs ORDER BY id DESC LIMIT 200').fetchall()
        runs = [dict(r) for r in rows]
    finally:
        db.close()
    return {'runs': runs}


@router.get('/calibration/runs/{run_id}')
def get_run(run_id: int):
    db = connect_db()
    try:
        ensure_calibration_table(db)
        row = db.execute('SELECT * FROM calibration_runs WHERE id=?', (run_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='not found')
        r = dict(row)
    finally:
        db.close()
    return r
