import threading
import time
import statistics
import json
import logging
from typing import Optional, Dict, Any

from app.db.persistence import get_persistence
from app.core.range_cache import get_range_cache

logger = logging.getLogger("pi.calibration")


class CalibrationManager:
    def __init__(self, persistence=None, range_cache=None):
        self.persistence = persistence or get_persistence()
        self.range_cache = range_cache or get_range_cache()
        self._active_run_id: Optional[int] = None
        self._active = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._progress: Dict[str, Any] = {}

    def is_active(self) -> bool:
        return self._active

    def get_active_run(self) -> Optional[Dict[str, Any]]:
        if not self._active_run_id:
            return None
        return self.persistence.get_calibration_run(self._active_run_id)

    def start(self, tag_mac: str, duration_ms: int = 6000, now_ms: Optional[int] = None) -> int:
        with self._lock:
            if self._active:
                raise RuntimeError("calibration already active")
            now_ms = now_ms or int(time.time() * 1000)
            params = {"v": 1, "type": "calibration", "tag_mac": tag_mac, "method": "median", "window_ms": duration_ms}
            run_id = self.persistence.create_calibration_run(tag_mac, json.dumps(params), now_ms)
            self._active_run_id = run_id
            self._active = True
            self._stop.clear()
            self._thread = threading.Thread(target=self._collect_and_compute, args=(run_id, tag_mac, duration_ms), daemon=True)
            self._thread.start()
            self.persistence.insert_event('INFO', 'calibration', 'calibration_start', tag_mac, json.dumps({'run_id': run_id}))
            return run_id

    def abort(self, now_ms: Optional[int] = None) -> None:
        with self._lock:
            if not self._active:
                return
            self._stop.set()
            now_ms = now_ms or int(time.time() * 1000)
            rid = self._active_run_id
            try:
                self.persistence.abort_calibration_run(rid, now_ms)
            except Exception:
                logger.exception("failed to abort run")
            self.persistence.insert_event('INFO', 'calibration', 'calibration_abort', '', json.dumps({'run_id': rid}))
            self._active = False
            self._active_run_id = None

    def _collect_and_compute(self, run_id: int, tag_mac: str, duration_ms: int):
        start = time.time()
        end_time = start + (duration_ms / 1000.0)
        sample_interval = 0.05
        samples_per_anchor = {}

        while time.time() < end_time and not self._stop.is_set():
            now_ms = int(time.time() * 1000)
            snaps = self.range_cache.snapshot(tag_mac, max_age_ms=duration_ms)
            for s in snaps:
                anchor = s.anchor_mac
                samples_per_anchor.setdefault(anchor, []).append(s.d_m)
            time.sleep(sample_interval)
            # update progress
            self._progress = {'run_id': run_id, 'elapsed_ms': int((time.time()-start)*1000), 'anchors_seen': len(samples_per_anchor)}

        # if aborted
        if self._stop.is_set():
            self.persistence.finish_calibration_run(run_id, 'ABORTED', int(time.time() * 1000))
            self._active = False
            self._active_run_id = None
            return

        # evaluate
        now_ms = int(time.time() * 1000)
        guards_min = int(self.persistence.get_setting('guards.min_anchors_online') or 4)
        anchors_used = [a for a, v in samples_per_anchor.items() if len(v) >= 3]
        if len(anchors_used) < guards_min or len(anchors_used) < 4:
            # fail
            self.persistence.finish_calibration_run(run_id, 'FAILED', now_ms, json.dumps({'anchors_used': anchors_used}), None)
            self.persistence.insert_event('WARN', 'calibration', 'calibration_failed', tag_mac, json.dumps({'run_id': run_id, 'reason': 'insufficient_anchors', 'anchors_seen': list(samples_per_anchor.keys())}))
            self._active = False
            self._active_run_id = None
            return

        # compute median per anchor and simple bias diagnostics
        biases = {}
        for a in anchors_used:
            vals = samples_per_anchor.get(a, [])
            med = statistics.median(vals)
            mad = statistics.pstdev(vals) if len(vals) > 1 else 0.0
            biases[a] = {'median_m': med, 'std_m': mad, 'count': len(vals)}

        summary = {'anchors_used': anchors_used, 'biases': biases}
        params = self.persistence.get_calibration_run(run_id)['params_json']
        self.persistence.finish_calibration_run(run_id, 'OK', now_ms, json.dumps(summary))
        self.persistence.insert_event('INFO', 'calibration', 'calibration_finish', tag_mac, json.dumps({'run_id': run_id, 'summary': summary}))
        # finalize
        self._active = False
        self._active_run_id = None
# Calibration manager
