# CODEX_TASK_PHASE2_UI_API_DB.md
Repo: **LightTracking**  
Ziel: **Phase-2 Umsetzung** (API + DB Migration + Web-UI + Live-Streaming), kompatibel zu Phase-1.

## 0. Rahmenbedingungen (nicht verhandelbar)
- **Pi ist Source of Truth**: persistiert in SQLite, kann per MQTT überschreiben/aktualisieren (wie bereits besprochen).
- **Primär-ID ist MAC** (Devices/Anchors/Tags).
- **Pi und Anchors im selben Netz**.
- MQTT: **1883 im isolierten LAN**, **MQTTS als späterer Hardening-Schritt**.
- Web-UI soll **direkt** gegen die FastAPI laufen (Jinja2 Templates + Static Assets), ohne externes Build-Tool.
- Phase-2 darf Phase-1 nicht brechen: **bestehende Endpoints bleiben kompatibel**.

---

## 1. Deliverables (Phase-2)
### 1.1 API Erweiterungen
1) **Anchors**
- `GET /api/v1/anchors`
  - liefert Liste inkl. Position und Online-Status
- `GET /api/v1/anchors/{mac}` (optional, falls sinnvoll)
- Optional: `PUT /api/v1/anchors/{mac}` für Alias/Role/Meta (oder über devices API)

2) **Calibration Wizard**
- `GET /api/v1/calibration/status`
  - `{running: bool, run_id: int|null, tag_mac: str|null, started_at_ms, progress: {samples, duration_ms, ...}}`
- `POST /api/v1/calibration/commit/{run_id}`
  - schreibt Ergebnis als „aktiv“ (Settings/DB) und markiert Run committed
- `POST /api/v1/calibration/discard/{run_id}`
  - markiert Run discarded
- `GET /api/v1/calibration/runs` und `GET /api/v1/calibration/runs/{run_id}` bleiben

3) **Fixtures**
- `enabled` unterstützen
- `POST /api/v1/fixtures/{id}/enable`
- `POST /api/v1/fixtures/{id}/disable`
  - alternativ (wenn gewünscht) `PATCH /api/v1/fixtures/{id}` mit `{"enabled": true/false}` – aber dann PATCH sauber integrieren
- Validierungen:
  - DMX Base Address Range (1..512)
  - optional: Kollisionen innerhalb Universe prüfen (wenn Profile Kanalanzahl bekannt)

4) **Live Streaming**
- WebSocket: `GET /ws/live`
  - streamt Position-Updates + state (SETUP/SAFE/LIVE) + mqtt_ok + age_ms
  - minimal: JSON Events `{"type":"pos","tag_mac":...,"position_cm":{x,y,z},"age_ms":...,"ts_ms":...}`
- WebSocket: `GET /ws/calibration` (optional, wenn Calibration progress live angezeigt wird)

### 1.2 DB Migration
- Migration System: `pi/app/db/migrations/` + idempotenter runner beim App-Start
- Schema Änderungen:
  - `fixtures`: add `enabled INTEGER NOT NULL DEFAULT 1`, `updated_at_ms INTEGER`
  - `calibration_runs`: add `status TEXT`, `committed_at_ms INTEGER`, `discarded_at_ms INTEGER`
  - optional: `anchors` view/table, falls `devices` nicht ausreichend ist
- Settings:
  - `calibration.active_run_id`
  - `calibration.active_params_json` (oder dedizierte Tabelle), abhängig von existierender Logik

### 1.3 Web-UI Erweiterungen
Basierend auf `pi/app/web/templates` + `pi/app/web/static/app.js`.

- **Anchors Seite**:
  - Tabelle: mac, alias, online, last_seen, x/y/z
  - Edit x/y/z in-place (nur in SETUP, blockiert in LIVE)
- **Calibration Seite**:
  - Start (wie Phase-1)
  - Live Status (poll `/calibration/status` oder ws)
  - Run-Detail
  - Buttons: Commit / Discard (nur in SETUP, blockiert in LIVE)
- **Fixtures Seite**:
  - enabled toggle (Enable/Disable)
  - Profile Dropdown (aus `/fixture-profiles`)
  - Edit/Delete wie Phase-1
- **Live Seite**:
  - WebSocket Stream (fallback: polling)
  - Anzeige: state, age_ms, pos, quality, last update time

### 1.4 Ops / Service (optional, aber empfohlen)
- `systemd` unit + env file
- `/api/v1/health` endpoint

---

## 2. Arbeitsplan (Implementation Steps)
### Step A — DB Migration Framework
1. Create: `pi/app/db/migrations/0002_phase2.sql`
2. Create: `pi/app/db/migrations/runner.py`
   - liest aktuelle version aus `settings` (key `db.schema_version`)
   - führt fehlende Migrationen sequenziell aus (idempotent)
3. Call runner from `app.main` Startup Event

**Akzeptanzkriterien**
- App startet mit bestehender Phase-1 DB ohne Fehler
- Schema-Änderungen sind nach Start vorhanden (PRAGMA table_info)

---

### Step B — Anchors API
1. Implement `GET /api/v1/anchors`
   - Aggregation aus `devices` + `anchor_positions`
   - Online: `last_seen_at_ms` innerhalb konfigurierbarer Schwelle (z.B. `anchors.online_window_ms`, default 5000)
2. UI: Anchors Tabelle + Position edit
3. Guards: Änderungen blockiert in LIVE (wie in routes_anchors.py)

**Akzeptanzkriterien**
- `curl http://localhost:8000/api/v1/anchors` liefert JSON Liste
- UI `/ui/anchors` zeigt Liste und erlaubt SETUP edits

---

### Step C — Fixtures enabled + endpoints
1. DB Migration: fixtures.enabled + updated_at_ms
2. Persistence layer:
   - list_fixtures liefert enabled
   - update_fixture schreibt updated_at_ms
3. API:
   - `POST /fixtures/{id}/enable`
   - `POST /fixtures/{id}/disable`
4. UI:
   - Toggle/Buttons in fixtures.html
   - Status sichtbar

**Akzeptanzkriterien**
- Enable/Disable funktioniert und bleibt nach Restart erhalten
- In LIVE sind Änderungen gesperrt (409 STATE_BLOCKED)

---

### Step D — Calibration Wizard (commit/discard/status)
1. DB: calibration_runs Felder
2. CalibrationManager erweitern:
   - status() liefert progress/running
   - commit(run_id) aktiviert Ergebnis (wo gespeichert wird: Settings oder Tabelle)
   - discard(run_id)
3. API routes:
   - `/calibration/status`
   - `/calibration/commit/{run_id}`
   - `/calibration/discard/{run_id}`
4. UI:
   - Status Poll / WS optional
   - Buttons Commit/Discard mit Guards

**Akzeptanzkriterien**
- Start → status zeigt running/progress
- commit markiert run committed und speichert aktive Parameter
- discard markiert run discarded
- UI zeigt Status und erlaubt Commit/Discard

---

### Step E — Live WebSocket
1. Implement `ws/live`:
   - Broadcast aus TrackingEngine (Positionsupdates)
   - On connect: send snapshot (state + last pos)
2. UI live.html:
   - connect ws
   - fallback polling wenn ws fail
3. Optional: ws/calibration

**Akzeptanzkriterien**
- Browser sieht Live Updates ohne Polling (WS)
- Server stabil bei reconnects

---

### Step F — Health + systemd (optional)
1. `/api/v1/health` (db ok + mqtt ok + engine ok)
2. `deploy/lighttracking.service` + `/etc/lighttracking.env` template

---

## 3. Code Constraints / Style
- Keine zirkulären Imports (Routes dürfen `app.main` nicht importieren).
- Zugriff auf Engine über `request.app.state.*`.
- SQLite connections sauber schließen; prefer helper `get_db_path()` und einheitlicher wrapper.
- UTF-8 Templates (keine Sonderbytes), keine großen Abhängigkeiten.

---

## 4. Test Protocol (minimal)
1. Start:
```bash
cd ~/LightTracking
./start.sh
```
2. API sanity:
```bash
curl -i http://localhost:8000/api/v1/state
curl -i http://localhost:8000/api/v1/fixtures
curl -i http://localhost:8000/api/v1/anchors
curl -i http://localhost:8000/api/v1/calibration/status
```
3. UI:
- `/ui` lädt ohne 500
- `/ui/fixtures` zeigt Liste und enabled toggle
- `/ui/calibration` zeigt Status + commit/discard
- `/ui/live` zeigt WS updates (oder fallback)

---

## 5. Git Commit Plan
- Commit 1: DB migrations framework + schema bump
- Commit 2: Anchors API + UI
- Commit 3: Fixtures enabled + UI
- Commit 4: Calibration wizard + UI
- Commit 5: Live WS + UI
- Commit 6: Ops/health (optional)

---

## 6. Acceptance Checklist (Final)
- [ ] App startet auf bestehender Phase-1 DB
- [ ] `/api/v1/anchors` existiert und UI zeigt Anchors
- [ ] Fixtures haben enabled + endpoints + UI toggle
- [ ] Calibration status + commit/discard implementiert + UI wizard
- [ ] Live WS funktioniert (fallback polling ok)
- [ ] Guards: Änderungen in LIVE blockiert mit 409
