# CODEX TASK – Phase 4 (Calibration Workflow + Invalidation + Wizard API)

## Ziel (Phase 4 Scope)
Implementiere Phase 4 im Repo **LightTracking**:
1) **Kalibrierungs-Workflow** (Start/Collect/Compute/Finish/Abort)
2) **Invalidation-Logik** (Anchor-Layout Änderungen invalidieren Kalibrierungen)
3) **Guards & Readiness**: vollständige Gates für LIVE
4) **Calibration API** gemäß OpenAPI v1 (start/abort/runs)
5) Optional: **Calibration Progress Push** via WebSocket

**Nicht enthalten in Phase 4:** Hardening (MQTTS/ACL), Firmware AT-Details (Phase 5), Advanced UI.

## Harte Vorgaben
- Kalibrierung läuft nur im Zustand **SETUP** und setzt System in **CALIBRATION**.
- Während CALIBRATION: DMX Test Aim darf laufen, aber LIVE ist gesperrt.
- Änderung an `anchor_positions` invalidiert aktive/validierte Kalibrierungen (invalidated_at_ms setzen).
- Pi bleibt Source of Truth; Calibration params werden in `calibration_runs.params_json` persistiert.
- Keine Scheinkalibrierung: wenn zu wenige valide Samples/Anchors -> result=FAILED mit reason.

---

## Deliverables (Phase 4)

### A) DB / Persistenz Erweiterungen (falls nötig)
**Dateien:**
- `pi/app/db/persistence.py`
- (Optional) neue Migration, falls Phase-1 Schema zu minimal ist

**calibration_runs Anforderungen (final v1):**
- id PK AUTOINCREMENT
- tag_mac
- started_at_ms
- ended_at_ms (nullable)
- result ENUM: OK/FAILED/ABORTED
- invalidated_at_ms (nullable)
- params_json (TEXT) – persistente Kalibrierparameter
- summary_json (TEXT) – z.B. rms_resid_m, anchors_used, per-anchor stats
- (optional) notes/reason

**Event Log:**
- events: calibration_start, calibration_finish, calibration_abort, calibration_failed, calibration_invalidated

### B) CalibrationManager Implementation
**Dateien:**
- `pi/app/core/calibration_manager.py`
- `pi/app/core/state_manager.py` (Guard integration)
- `pi/app/core/range_cache.py` (Sampling support)

**Public API (konkret):**
- `start(tag_mac: str, duration_ms: int, now_ms: int) -> int(run_id)`
- `abort(now_ms: int) -> None`
- `is_active() -> bool`
- `get_active_run() -> dict | None` (für progress)

**Sampling / Compute (v1 robust):**
- Collect window: duration_ms (default 6000)
- Sample source: RangeCache snapshot repetitiv (z.B. alle 50ms) oder direkt ingest sammeln
- Mindestanforderungen:
  - min anchors online: guards.min_anchors_online
  - min anchors with positions: >=4
  - pro anchor mindestens N samples (default 10) oder ausreichende coverage
- Compute:
  - per anchor: median distance (robust), MAD/STD, invalid sample ratio
  - global: derive params_json (v1 minimal zulässig):
    - { "v":1, "type":"calibration", "tag_mac":..., "method":"median", "window_ms":..., "anchors_used":[...], "dist_bias_m":{anchor_mac: bias}, "notes":... }
  - Bias/Offsets (v1):
    - Implementiere zunächst als *diagnostische* Parameter, die später in Tracking als Weight/Bias einfließen können.
    - Tracking muss Phase 4 noch nicht verändern, außer: LIVE requires valid calibration.
- Finish:
  - Persist calibration_runs: result OK/FAILED/ABORTED
  - Set system state zurück zu SETUP
  - Publish optional MQTT cmd `apply_calibration_params` an Geräte (nur wenn sinnvoll; sonst TODO + Logging)

### C) Invalidation Logic
**Dateien:**
- `pi/app/db/persistence.py`
- `pi/app/api/routes_anchors.py` (hook bei position update/bulk)
- optional: `pi/app/core/state_manager.py`

**Regel:**
- Jeder Upsert in `anchor_positions` führt zu:
  - `invalidate_calibrations(now_ms)` (global oder per tag)
  - event_log WARN/INFO calibration_invalidated
- Wenn ein calibration run aktiv ist, darf er weiterlaufen, aber nach update muss er FAILen oder neu gestartet werden.
  - v1 Policy: Wenn anchor_positions während active calibration geändert werden -> abort active calibration + mark ABORTED + invalidated.

### D) Guards / Readiness finalisieren
**Dateien:**
- `pi/app/core/state_manager.py`
- `pi/app/api/routes_state.py`

**Gates (final v1):**
- mqtt_ok (connected)
- anchors_online >= guards.min_anchors_online
- anchors_missing_positions empty
- tag_online ok (min 1 oder selected primary tag)
- calibration_ok: latest valid calibration exists for primary tag (invalidated_at_ms is null, result=OK)
- dmx_ok: driver initialized (or can initialize)
- fixtures_ok: enabled fixtures >=1

**State Transition Policy:**
- SETUP -> LIVE nur wenn alle Gates ok
- SETUP -> CALIBRATION nur wenn anchors online + positions ok + tag online
- LIVE -> SAFE jederzeit, SAFE -> SETUP jederzeit
- CALIBRATION -> SETUP automatisch am Ende

### E) REST API: Calibration Endpoints
**Dateien:**
- `pi/app/api/routes_calibration.py`
- `pi/app/main.py` router include

**Endpoints:**
- `POST /api/v1/calibration/start` {tag_mac, duration_ms} -> {ok, run_id}
- `POST /api/v1/calibration/abort` -> {ok}
- `GET /api/v1/calibration/runs` (optional filter tag_mac) -> {runs[]}
- `GET /api/v1/calibration/runs/{id}` -> detail (params + summary)

**Errors:**
- 409 STATE_BLOCKED wenn falscher system.state oder gates nicht erfüllt
- 400 VALIDATION_ERROR für payload

### F) Optional: WebSocket Progress
- Push message types:
  - calibration_progress: {run_id, elapsed_ms, samples_collected, anchors_seen}
  - calibration_finished: {run_id, result, summary}

---

## Tests (minimum)
Unter `pi/app/tests/`:
1) `test_calibration_manager.py`:
   - synthetic samples -> OK
   - insufficient samples -> FAILED
   - abort -> ABORTED
2) `test_calibration_api.py`: start/abort/runs
3) `test_invalidation.py`: anchor position update invalidates calibration

---

## Definition of Done (Phase 4)
- Kalibrierung kann über API gestartet/abgebrochen werden.
- Runs werden korrekt in SQLite persistiert.
- LIVE wird zuverlässig geblockt, wenn keine gültige Kalibrierung existiert.
- Anchor position update invalidiert Kalibrierungen deterministisch.
- Tests grün und event_log sauber befüllt.
