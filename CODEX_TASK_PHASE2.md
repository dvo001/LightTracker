# CODEX TASK – Phase 2 (Range Cache + Trilateration + Tracking Engine + Tracking API)

## Ziel (Phase 2 Scope)
Implementiere Phase 2 im Repo **LightTracking**:
1) **Range Cache** (Ingest & Snapshot-Fusion)
2) **3D Trilateration** (WLS/LM + Robustheit)
3) **Tracking Engine** (Tick-basiert, States TRACKING/STALE/LOST, publish PositionPayload)
4) **Tracking API** (read-only) gemäß OpenAPI v1: `/tracking/*`
5) Optional: **position_log** (downsampled) + minimal retention hook

**Nicht enthalten in Phase 2:** DMX Output, Fixture Mapping, Calibration Workflow (nur Interfaces bleiben).

## Harte Vorgaben
- Verwende die bestehende Phase-1 Persistenz und Settings Keys (`rates.global`, `tracking.*`).
- Einheiten strikt: Device-Ranges **Meter (m)**, interne Geometrie **Zentimeter (cm)**.
- Determinismus: Gleiche Inputs → gleicher Output.
- Kein „Hiding“ von Fehlern: bei invaliden Samples/WLS-Failure muss ein sauberer Zustand (STALE/LOST) entstehen, plus event_log.

---

## Deliverables (Phase 2)

### A) MQTT Ingest: Range-Batches an RangeCache übergeben
**Dateien:**
- `pi/app/mqtt/mqtt_manager.py` (falls nötig erweitern)
- `pi/app/core/range_cache.py`
- `pi/app/mqtt/payloads.py` (Schemas)
- `pi/app/core/device_registry.py` (nur falls nötig)

**Behavior:**
- `dev/+/ranges` Payload parsen und in `RangeCache.update_from_batch()` einspeisen.
- Malformed payload: `event_log` ERROR, kein Crash.
- Range-Batch Schema (tolerant): akzeptiere `anchor_mac` aus Payload oder Topic; `ranges[]` enthält `tag_mac`, `d_m`, optional `q/nlos/err`.

### B) RangeCache: Snapshot-Fusion
**Dateien:**
- `pi/app/core/range_cache.py`

**Anforderungen:**
- Speicherstruktur pro (tag_mac, anchor_mac) -> latest sample
- `snapshot(tag_mac, max_age_ms)`:
  - liefert pro Anchor max. 1 Sample (latest)
  - nur Samples mit `now_ms - ts_ms <= max_age_ms`
- Thread-sicher (Lock oder copy-on-write)
- Unit Tests: windowing, overwrite, stale filtering

### C) Trilateration: solve_3d (WLS/LM)
**Dateien:**
- `pi/app/core/trilateration.py`

**Implementierung (v1 robust):**
- Eingabe: `anchor_positions_cm: dict[mac->Vec3Cm]`, `samples: list[RangeSample]`, `initial_pos_cm` optional
- min anchors: 4 (3D)
- Objective: min Σ w_i (||x - a_i|| - d_i)^2
- Gewichte: default 1.0, optional aus `q`
- LM steps:
  - max_iter (default 12)
  - stop, wenn step < eps_step_cm (default 0.2)
- Robustheit:
  - Plausibility: `d_min_cm`, `d_max_cm`
  - Residual gating: wenn `resid_m > resid_max_m` -> return None + metrics
  - Optional outlier removal: drop worst residual anchor, retry once, wenn anchors>=min+1
- Output:
  - pos_cm (oder None)
  - metrics: anchors_used, resid_m, iterations, outliers(list), reason(optional)

**Unit Tests:**
- synthetic geometry: 4–6 anchors, known point
- noise: resid below threshold
- outlier: worst anchor dropped improves solution
- insufficient anchors -> None

### D) TrackingEngine: Tick Loop + State Machine
**Dateien:**
- `pi/app/core/tracking_engine.py`
- optional helper `pi/app/core/tracking_state.py`

**Behavior:**
- tick rate: `rates.global.tracking_hz`
- stale_timeout_ms / lost_timeout_ms aus `rates.global`
- Tag set: online TAG devices aus DeviceRegistry (role=TAG, status ONLINE)
- Für jedes Tag:
  - samples = RangeCache.snapshot(tag, max_age_ms=stale_timeout_ms)
  - anchor_positions = aus DB (nur Anchors mit Position)
  - solve_3d -> pos or None
  - state:
    - TRACKING wenn pos valid
    - STALE wenn last_valid_age <= lost_timeout_ms und aktuell keine pos
    - LOST wenn last_valid_age > lost_timeout_ms
  - publish `tracking/<tag>/position` (QoS0) bei jedem tick (oder mindestens bei changes; v1: jede Tick ok)
  - Cache `latest_position[tag]` (für API + später DMX)
- Logging:
  - state changes als event_log INFO
  - solver failures als WARN (rate-limited)

### E) API: Tracking Endpoints
**Dateien:**
- `pi/app/api/routes_tracking.py`
- `pi/app/main.py` (Router include)

**Endpoints:**
- `GET /api/v1/tracking/tags` -> list of tags + current state
- `GET /api/v1/tracking/position/{tag_mac}` -> latest cached PositionPayload or 404

### F) Optional: position_log (Downsampled)
- Wenn `settings.logging.position_log.enabled=true`:
  - write to DB at `logging.position_log.hz` (default 5 Hz)
  - schema: (ts_ms, tag_mac, x_cm, y_cm, z_cm, state, anchors_used, resid_m, q)
- retention optional später

---

## Tests (minimum)
Unter `pi/app/tests/`:
1) `test_range_cache.py`
2) `test_trilateration.py` (realistic synthetic)
3) `test_tracking_engine_smoke.py`:
   - feed synthetic range batches
   - run a few ticks
   - assert published payload structure (mock mqtt publish) and API returns latest
4) `test_tracking_api.py` with TestClient

---

## Definition of Done (Phase 2)
- Tracking tick läuft im Hintergrund (Thread/async task) ohne Crash.
- Synthetic replay: Range-Batches erzeugen stabile PositionPayloads.
- `/api/v1/tracking/*` liefert konsistent Daten.
- Unit tests grün.
- Event log erfasst state changes und Solver-Warnungen.
