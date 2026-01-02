import time
import json
from typing import Dict, Any, List, Optional

from app.core.range_cache import RangeCache
from app.db.persistence import get_persistence


class CalibrationManager:
    def __init__(self, range_cache: RangeCache):
        self.range_cache = range_cache
        self.active: Optional[Dict[str, Any]] = None
        self.p = get_persistence()

    def start(self, tag_mac: str, duration_ms: int) -> int:
        if self.active:
            raise RuntimeError("calibration already running")
        db = self.p
        ts = int(time.time() * 1000)
        params = {"duration_ms": duration_ms}
        # persist run
        db_conn = db
        conn = db_conn  # alias
        # manual insert since persistence has no method
        connsql = conn
        run_id = None
        dbh = connsql
        # Use direct connect_db instead of persistence to insert row
        from app.db import connect_db
        cdb = connect_db()
        try:
            cur = cdb.execute(
                "INSERT INTO calibration_runs(tag_mac, started_at_ms, status, params_json) VALUES (?,?,?,?)",
                (tag_mac, ts, "running", json.dumps(params)),
            )
            cdb.commit()
            run_id = cur.lastrowid
        finally:
            cdb.close()

        self.active = {
            "run_id": run_id,
            "tag_mac": tag_mac,
            "started_at_ms": ts,
            "duration_ms": duration_ms,
            "samples": [],
        }
        return run_id

    def abort(self):
        if not self.active:
            return
        run_id = self.active["run_id"]
        ts = int(time.time() * 1000)
        from app.db import connect_db
        cdb = connect_db()
        try:
            cdb.execute("UPDATE calibration_runs SET ended_at_ms=?, result=?, status=? WHERE id=?", (ts, "ABORTED", "aborted", run_id))
            cdb.commit()
        finally:
            cdb.close()
        self.active = None

    def tick(self):
        """Collect samples while active; finish when duration elapsed."""
        if not self.active:
            return
        now = int(time.time() * 1000)
        start = self.active["started_at_ms"]
        dur = self.active["duration_ms"]
        if now - start < dur:
            snaps = self.range_cache.snapshot(self.active["tag_mac"], max_age_ms=dur)
            self.active["samples"].extend(snaps)
            self.active["progress"] = {"samples": len(self.active["samples"]), "duration_ms": now - start}
            return
        # finish
        self._finish(now)

    def _finish(self, ts_end: int):
        snaps = self.active.get("samples", [])
        anchors_used = list({s.anchor_mac for s in snaps})
        per_anchor = {}
        for s in snaps:
            per_anchor.setdefault(s.anchor_mac, []).append(s.d_m)
        per_anchor_stats = {k: {"median_d_m": sorted(v)[len(v)//2], "count": len(v)} for k, v in per_anchor.items()}
        summary = {
            "samples": len(snaps),
            "anchors_used": anchors_used,
            "duration_ms": self.active["duration_ms"],
            "result": "OK" if len(anchors_used) >= 2 else "FAILED",
            "per_anchor": per_anchor_stats,
        }
        result = summary["result"]
        params_json = json.dumps({"v": 1, "method": "median", "anchors_used": anchors_used, "per_anchor": per_anchor_stats})
        from app.db import connect_db
        cdb = connect_db()
        try:
            cdb.execute(
                "UPDATE calibration_runs SET ended_at_ms=?, result=?, status=?, summary_json=?, params_json=? WHERE id=?",
                (ts_end, result, "finished", json.dumps(summary), params_json, self.active["run_id"]),
            )
            cdb.commit()
        finally:
            cdb.close()
        self.active = None

    def status(self) -> Dict[str, Any]:
        if not self.active:
            return {"running": False, "run_id": None, "tag_mac": None, "started_at_ms": None, "progress": {}}
        return {
            "running": True,
            "run_id": self.active.get("run_id"),
            "tag_mac": self.active.get("tag_mac"),
            "started_at_ms": self.active.get("started_at_ms"),
            "progress": self.active.get("progress", {}),
        }
