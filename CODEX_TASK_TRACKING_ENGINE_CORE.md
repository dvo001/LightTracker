# CODEX_TASK_TRACKING_ENGINE_CORE.md
Repo: **LightTracking**  
Ziel: **TrackingEngine Core** implementieren (MQTT Ingestion → RangeStore → Solver → API), **ohne UI-Arbeit**.  
Priorität: schnell **End-to-End Tracking** lauffähig machen, robust gegen Ausreißer, ohne Circular Imports.

---

## 0) Rahmenbedingungen (fix)
- **Pi ist Source of Truth** (persistiert in SQLite, Settings steuern Runtime).
- **MAC ist Primär-ID** (anchors/tags).
- MQTT default **1883** im isolierten LAN.
- **Range-Batch Payload pro Anchor** ist das Input-Format.
- **3D direkt** (x,y,z in cm), **Freeze** ist ok.
- **Keine zirkulären Imports**: Routes dürfen **niemals** `app.main` importieren.

---

## 1) Deliverables
### 1.1 MQTT Ingestion (Anchor → Pi)
- MQTT Subscriber (paho-mqtt) subscribed auf:
  - `lighttracking/anchors/+/range_batch`
  - optional: `lighttracking/anchors/+/status`
- Callback macht nur:
  - JSON parse + minimale Validierung
  - Upsert `devices.last_seen_at_ms` (role='ANCHOR' wenn neu)
  - Enqueue Event in eine Queue (kein Rechnen im Callback)

### 1.2 RangeStore (rolling window)
- In-memory Store: `ranges[tag_mac][anchor_mac] -> deque[RangeSample]`
- RangeSample: `ts_ms, distance_mm, quality(optional), rssi(optional)`
- Konfigurierbar via Settings:
  - `tracking.window_ms` default 1500
  - `tracking.max_samples_per_pair` default 30
- Aggregation bei Snapshot:
  - Median der samples im Fenster (robust gegen Ausreißer)

### 1.3 AnchorCache (Positionen + Online-Status)
- Cache liefert:
  - Anchor Positionen aus `anchor_positions` (cm)
  - Online Status aus `devices.last_seen_at_ms` mit `anchors.online_window_ms` default 8000
- Refresh-Mechanik:
  - `anchor_cache_refresh_ms` default 1000
- Solver nutzt nur Anchors:
  - online == True
  - position vorhanden

### 1.4 Solver (Trilateration 3D, robust)
- Implementiere `solve_position_3d(anchor_positions_cm, distances_mm, initial_guess_cm=None)`
- Algorithmus: nichtlineare Least Squares (Gauss-Newton oder LM)
- Input:
  - dict anchor_mac -> (x_cm,y_cm,z_cm)
  - dict anchor_mac -> distance_mm
- Output:
  - `pos_cm (x,y,z)`
  - `residual_rms_mm`
  - `anchors_used`
- Quality:
  - `quality = clamp(1.0 - residual_rms_mm/residual_max_mm, 0, 1)`

Settings:
- `tracking.min_anchors` default 4
- `tracking.residual_max_mm` default 900 (tuning later)
- `tracking.max_iters` default 20
- `tracking.tol` default 1e-3

### 1.5 TrackingEngine (Worker + Freeze)
- Engine besitzt:
  - `queue` (bounded)
  - `range_store`
  - `anchor_cache`
  - `latest_position: dict[tag_mac, payload]`
  - `latest_good_position: dict[tag_mac, payload]`
- Periodischer Solve Loop (Thread oder asyncio task):
  - alle `tracking.solve_interval_ms` default 100
  - pro Tag:
    - snapshot distances aus range_store
    - filter auf online anchors + pos
    - wenn >= min_anchors:
      - solve, wenn residual ok → state TRACKING_OK
      - sonst → freeze/no_fix Logik
    - wenn < min_anchors → freeze/no_fix Logik

Freeze Settings:
- `tracking.freeze_hold_ms` default 2000
- Zustände:
  - `TRACKING_OK`
  - `FROZEN`
  - `NO_FIX`

### 1.6 API Wiring (Phase-1 kompatibel)
Routes müssen Engine aus `request.app.state.tracking_engine` lesen.

- `GET /api/v1/tracking/tags`
  - liefert Liste: `tag_mac,state,age_ms,anchors_used,quality,last_ts_ms`
- `GET /api/v1/tracking/position/{tag_mac}`
  - liefert kompletten payload

**Wichtig:** Entferne/ersetze jede Zeile, die `from app.main import ...` macht.
Routes dürfen nur `fastapi` + core/db module importieren.

### 1.7 Start/Startup Integration
In `app.main` Startup:
- migrations/DB init (bestehend)
- `mqtt_client.start()` (bestehend oder neu)
- `tracking_engine = TrackingEngine(persistence, settings)`
- `app.state.tracking_engine = tracking_engine`
- mqtt handler bekommt Referenz auf `tracking_engine.enqueue_range_batch(...)`

---

## 2) Payload Contract (fix für Phase-2 Core)
**Topic:** `lighttracking/anchors/{anchor_mac}/range_batch`  
**Payload JSON minimal:**
```json
{
  "anchor_mac":"AA:BB:CC:DD:EE:01",
  "ts_ms":1735590000123,
  "ranges":[
    {"tag_mac":"AA:BB:CC:DD:EE:99","distance_mm":5340,"quality":0.82,"rssi":-71}
  ],
  "seq":12345
}
```
---

## Implementierung (durch Codex)

Die TrackingEngine-Core-Komponenten wurden implementiert und dem App-Startup hinzugefügt. Geänderte / neu angelegte Dateien:

- [pi/app/core/solver.py](pi/app/core/solver.py)
- [pi/app/core/range_store.py](pi/app/core/range_store.py)
- [pi/app/core/anchor_cache.py](pi/app/core/anchor_cache.py)
- [pi/app/core/tracking_engine.py](pi/app/core/tracking_engine.py)
- [pi/app/core/__init__.py](pi/app/core/__init__.py)
- [pi/app/api/routes_tracking.py](pi/app/api/routes_tracking.py)
- [pi/app/api/__init__.py](pi/app/api/__init__.py) (router registration)
- [pi/app/mqtt_client.py](pi/app/mqtt_client.py)
- [pi/app/main.py](pi/app/main.py) (startup: attach tracking_engine + mqtt_client)

### Runbook (Kurz)

Env vars:
- `LT_DB_PATH` (optional) — sqlite DB path
- `MQTT_HOST` (optional, default `localhost`)
- `MQTT_PORT` (optional, default `1883`)

Start (dev):
```bash
uvicorn pi.app.main:app --reload --port 8000
```

Smoke-test:
```bash
mosquitto_pub -h ${MQTT_HOST:-localhost} -t "lighttracking/anchors/AA:BB:CC:DD:EE:01/range_batch" -m '{"anchor_mac":"AA:BB:CC:DD:EE:01","ts_ms":'"$(date +%s%3N)"',"ranges":[{"tag_mac":"AA:BB:CC:DD:EE:99","distance_mm":5000}],"seq":1}'
curl http://localhost:8000/api/v1/tracking/tags
curl http://localhost:8000/api/v1/tracking/position/AA:BB:CC:DD:EE:99
```

Hinweis: MQTT-Client nutzt `paho-mqtt` falls installiert; ist das Paket nicht verfügbar, läuft die Engine ohne MQTT-Ingest (manuelles Publizieren per mosquitto_pub wird dann benötigt).

Rules:
- anchor_mac darf aus Topic abgeleitet werden; falls Payload anchor_mac abweicht → Event log WARN + drop.
- distance_mm muss >0 und plausibel sein (z. B. < 100000mm).

---

## 3) DB Anforderungen (minimal)
Muss vorhanden sein:
- `devices(mac PRIMARY KEY, role, first_seen_at_ms, last_seen_at_ms, ...)`
- `anchor_positions(mac PRIMARY KEY, x_cm,y_cm,z_cm, updated_at_ms)`
- `settings(key PRIMARY KEY, value, updated_at_ms)`
Optional (nur logging):
- `event_log(...)`

Wenn Tabellen fehlen: implementiere Migration oder safe-create (idempotent).

---

## 4) Logging / Events (minimal)
- MQTT connect/disconnect → event_log INFO/WARN
- Queue overflow drops → event_log WARN
- Solver fail (residual) → event_log DEBUG/WARN (rate limited)

---

## 5) Tests (Smoke)
### 5.1 Unit-ish
- Solver: mit 4 Anchors (tetra) + synthetischen Distances muss Position ~stimmen
- RangeStore: median aggregation korrekt

### 5.2 Manual
1. Start server
2. Publish test message (mosquitto_pub):
```bash
mosquitto_pub -h localhost -t "lighttracking/anchors/AA:BB:CC:DD:EE:01/range_batch" -m '{"anchor_mac":"AA:BB:CC:DD:EE:01","ts_ms":1735590000123,"ranges":[{"tag_mac":"AA:BB:CC:DD:EE:99","distance_mm":5000}],"seq":1}'
```
3. Check API:
```bash
curl http://localhost:8000/api/v1/tracking/tags
curl http://localhost:8000/api/v1/tracking/position/AA:BB:CC:DD:EE:99
```

---

## 6) Output-Anforderungen von Codex
- Zeige nach Umsetzung:
  - Liste der geänderten/neu angelegten Dateien
  - Kurzer Runbook Abschnitt: wie starten, welche env vars
- Kein UI verändern.
- Nach jedem größeren Block (MQTT, RangeStore, Solver, Engine, Routes) kurz stoppen und diff anzeigen.

---

## 7) Codex Prompt (1:1 verwenden)
Implementiere TrackingEngine Core gemäß dieser Datei in **LightTracking**.
Arbeite in der Reihenfolge: MQTT → RangeStore → AnchorCache → Solver → TrackingEngine → API Routes → Startup Integration.
Achte strikt auf: **keine Circular Imports**, **keine UI-Änderungen**, **MQTT Callback nicht blockierend**.
Zeige nach jedem Block die geänderten Dateien und relevante Codeausschnitte.
