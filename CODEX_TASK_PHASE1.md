# CODEX TASK – Phase 1 (DB + API Skeleton + MQTT Ingest)

## Ziel (Phase 1 Scope)
Implementiere Phase 1 des Projekts im Repo **uwb_tracking_dmx_repo**:
1) **SQLite Migration Runner + Schema + Seeds**
2) **FastAPI App Skeleton** inkl. Health/State Endpoints und saubere Modulstruktur
3) **MQTT Ingest Grundgerüst** (connect/subscribe + parsing callbacks + event_log)

**Nicht enthalten in Phase 1:** Trilateration, Tracking Engine, DMX Output, Calibration Logic (nur Platzhalter-Interfaces, kein Verhalten).

## Harte Vorgaben
- Nutze die vorhandene Ordnerstruktur unter `pi/app/...`.
- Pi ist Source of Truth, Persistenz in SQLite.
- Keine Dummy-Funktionalität, die spätere Phasen behindert. Stubs nur als Interface mit TODO + Logging.
- Alle Module müssen importierbar sein; `uvicorn` Start muss funktionieren.
- Schreibe mindestens **Smoke Tests** für DB-Migrationen und API-Routes.

---

## Deliverables (Phase 1)

### A) DB: Migration Runner + Schema + Seed
**Dateien:**
- `pi/app/db/database.py`
- `pi/app/db/persistence.py`
- `pi/app/db/migrations/0001_init_schema.sql`
- `pi/app/db/migrations/0002_seed_defaults.sql`

**DB Anforderungen:**
- `PRAGMA foreign_keys=ON`
- `PRAGMA journal_mode=WAL`
- Tabelle `schema_migrations(version PK, name, applied_at_ms)`
- Tabellen (v1 minimal, ohne optionale Logs ok, aber empfohlen):
  - `devices(mac PK, role, alias, name, ip_last, fw, first_seen_at_ms, last_seen_at_ms, status, notes)`
  - `device_settings(mac, key, value, updated_at_ms, PK(mac,key))`
  - `settings(key PK, value, updated_at_ms)`
  - `anchor_positions(mac PK, x_cm, y_cm, z_cm, updated_at_ms)`
  - `fixture_profiles(profile_key PK, profile_json, updated_at_ms)`
  - `fixtures(id PK AUTOINCREMENT, ... )` (Schema darf in Phase 1 minimal sein, aber Tabelle muss existieren)
  - `calibration_runs(id PK AUTOINCREMENT, tag_mac, started_at_ms, ended_at_ms, result, invalidated_at_ms, params_json, summary_json)`
  - `event_log(id PK AUTOINCREMENT, ts_ms, level, source, event_type, ref, details_json)`
  - optional: `position_log`, `range_log` (kann Phase 2/3 folgen)

**Seed Anforderungen (0002_seed_defaults.sql):**
- `system.state = "SETUP"`
- `rates.global` JSON (tracking_hz, dmx_hz, ui_hz, stale_timeout_ms, lost_timeout_ms)
- `guards.min_anchors_online=4` und require_* flags (strings "true"/"false" ok)
- `tracking.mode="3D"`, `tracking.loss_behavior="freeze"`
- `dmx.output_driver="uart_rs485"`, `dmx.uart_device="/dev/serial0"`
- Logging Defaults (position_log enabled/hz, event_log retention)
- `fixture_profiles`: seed `generic_mh_16bit_v1` (profile_json als JSON-String; Inhalte können v1 minimal sein)

**Migration Runner:**
- In `persistence.py` oder separatem Helper: `migrate()` liest SQL-Dateien aus `migrations/`, führt nur fehlende Versionen aus.
- Jede Migration transaktional ausführen (soweit SQLite möglich).

### B) FastAPI App Skeleton
**Dateien:**
- `pi/app/main.py`
- `pi/app/config.py`
- `pi/app/api/routes_state.py`
- `pi/app/api/routes_settings.py`
- `pi/app/api/routes_devices.py`
- `pi/app/api/routes_events.py`
- (Optional) `pi/app/api/websocket.py` als Stub

**Anforderungen:**
- `main.py` startet FastAPI, ruft beim Start `Persistence.migrate()` auf.
- Provide dependency injection für Persistence (z.B. global singleton oder FastAPI dependency).
- Implementiere Phase-1-Endpunkte (subset von OpenAPI):
  - `GET /api/v1/state` → liefert `system.state` + minimal readiness (mqtt_ok, anchors_online count, etc. darf placeholder sein)
  - `POST /api/v1/state` → nur SETUP/SAFE zulassen in Phase 1 (LIVE/CALIBRATION: return 409 mit STATE_BLOCKED)
  - `GET /api/v1/settings` + `PUT /api/v1/settings`
  - `GET /api/v1/devices` + `PUT /api/v1/devices/{mac}` + `DELETE /api/v1/devices/{mac}`
  - `GET /api/v1/events`
- Modellierung: nutze Pydantic-Modelle, konsistente ErrorResponse Struktur.

### C) MQTT Ingest Grundgerüst
**Dateien:**
- `pi/app/mqtt/mqtt_manager.py`
- `pi/app/mqtt/topics.py`
- `pi/app/mqtt/payloads.py`
- `pi/app/core/device_registry.py` (Phase 1 light)
- (Optional) `pi/app/core/range_cache.py` nur als Interface/Dataclass, keine Tracking Logik

**Anforderungen:**
- Verwende `paho-mqtt`.
- Konfiguration: Broker host/port aus SQLite settings (fallback env vars ok).
- Subscriptions (Phase 1):
  - `dev/+/status`
  - `dev/+/cmd_ack`
  - `dev/+/ranges` (nur parsen + loggen, noch kein Tracking)
- Callbacks:
  - on status: upsert in `devices`, update last_seen_at_ms, status ONLINE, role aus Payload (falls vorhanden)
  - on malformed payload: event_log ERROR mit details_json
- MQTT Laufzeit: starte MQTT in einem background thread beim FastAPI startup (sauber stoppbar beim shutdown).

**Payload expectations (Phase 1 minimal):**
- `dev/<mac>/status` JSON: `{v,type,mac,role,fw,ip,ts_ms,status}` (tolerant parsen; mac aus topic möglich)
- `dev/<mac>/ranges` JSON: nur validieren und loggen (no-op)
- `dev/<mac>/cmd_ack` JSON: loggen + optional in-memory pending list (stub ok)

---

## Tests (minimum)
Lege unter `pi/app/tests/` folgende Smoke Tests an:
1) `test_migrations.py`: create temp sqlite, run migrate(), assert tables exist, assert seeds exist.
2) `test_api_smoke.py`: FastAPI TestClient, GET /api/v1/state returns 200, settings roundtrip works.
3) Optional: `test_devices_api.py`: create/update/list/delete device.

---

## Definition of Done (Phase 1)
- `pip install -r pi/requirements.txt` erfolgreich.
- `uvicorn pi.app.main:app --reload` startet ohne Fehler.
- Migrationen laufen automatisch beim Start.
- API subset funktioniert (smoke tests grün).
- MQTT thread startet und subscribed (auch ohne Broker darf App nicht crashen; dann event_log WARN und retry/backoff).

---

## Hinweis für Codex
Arbeite commit-fähig und hinterlasse klare TODOs für Phase 2 (Tracking/Trilateration) und Phase 3 (DMX).
