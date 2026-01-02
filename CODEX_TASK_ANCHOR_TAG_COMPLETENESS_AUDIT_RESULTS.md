# Audit — Anchor/Tag Completeness (Deep Audit Results)

Ergebnis eines zeilen-genauen Scans; Status, Belege und konkrete Fix-Vorschläge.

| Checkpunkt | Status | Datei:Zeilen | Begründung (kurz) | Fix-Vorschlag (konkret) |
|---|---:|---|---|---|
| MAC als Primär-ID überall | TEIL | [pi/app/api/routes_anchors.py](pi/app/api/routes_anchors.py#L22-L22), [pi/app/api/routes_anchors.py](pi/app/api/routes_anchors.py#L48-L65) | Anchors-API verwendet `mac` PK; `devices`-table/usage nicht klar im Pi-Code | Suche/vereinheitliche `devices`-Schema auf `mac` PK; dokumentiere mapping
| Pi als Source-of-Truth (SQLite) | OK | [pi/app/db/__init__.py](pi/app/db/__init__.py#L1-L12), [pi/app/db/migrations/runner.py](pi/app/db/migrations/runner.py#L1-L30) | `connect_db()` + migrations runner beim Startup vorhanden | Dokumentiere `LT_DB_PATH` in Deploy-Scripts; Backup-Policy
| State Machine / Guards | FEHLT | [pi/app/api/routes_state.py](pi/app/api/routes_state.py#L1-L40) | `system_state` ist statisch `SETUP`; kein StateManager/Guards implementiert | Implementiere `app.state.system_state` und prüfe in write-APIs (409 on LIVE)
| MQTT ingestion for Anchor Ranges | FEHLT | UI & health reference: [pi/app/web/static/app.js](pi/app/web/static/app.js#L84-L92), [pi/app/api/routes_health.py](pi/app/api/routes_health.py#L20-L30) | UI/Health erwarten `mqtt_ok`, aber kein MQTT-Client/handler im Pi gefunden | Add MQTT startup client (asyncio/paho), handlers for range_batch → persist
| Topic schema consistency | FEHLT | (no central topic file found) | No canonical topic schema in repo; firmware may document topics elsewhere | Define canonical topic schema (e.g. `lighttracking/anchors/{mac}/range_batch`), add doc + validation
| Payload validation | FEHLT | UI expects tracking endpoints: [pi/app/web/static/app.js](pi/app/web/static/app.js#L18-L19); no payload models observed | Add pydantic models for RangeBatch payloads and validate on MQTT receive
| devices Upsert & online status | TEIL | [pi/app/api/routes_anchors.py](pi/app/api/routes_anchors.py#L20-L34), UI anchors list: [pi/app/web/static/app.js](pi/app/web/static/app.js#L128-L137) | Anchors API exposes `last_seen_at_ms` from `anchor_positions` or `anchors` table; no centralized upsert endpoint | Add `POST /api/v1/devices/upsert` or ensure existing ingestion writes `first_seen_at_ms/last_seen_at_ms/role`
| Anchor position API + Guard | TEIL | [pi/app/api/routes_anchors.py](pi/app/api/routes_anchors.py#L64-L71), state: [pi/app/api/routes_state.py](pi/app/api/routes_state.py#L1-L40) | `POST /anchors/position` exists and writes `anchor_positions` but lacks LIVE-guard | Add guard in `upsert_anchor` using `app.state.system_state`
| TrackingEngine (positions) | FEHLT | UI expects tracking endpoints: [pi/app/web/static/app.js](pi/app/web/static/app.js#L18-L19); no `TrackingEngine` module found | Implement `TrackingEngine` module consuming range_batches and writing `latest_positions`
| API tracking endpoints | FEHLT | UI calls: [pi/app/web/static/app.js](pi/app/web/static/app.js#L18-L19); API routers: [pi/app/api/__init__.py](pi/app/api/__init__.py#L1-L10) | `routes_tracking` not present in included routers | Add `routes_tracking.py` with `GET /tracking/tags` and `/tracking/position/{tag_mac}` returning `state+position_cm+age_ms+ts_ms`
| Circular imports | OK | [pi/app/api/__init__.py](pi/app/api/__init__.py#L1-L10), [pi/app/main.py](pi/app/main.py#L34-L40) | Routes are modular and included by the api router; no obvious cycles detected | Maintain import hygiene during refactors
| Broadcaster / WebSocket anchor_pos | OK | [pi/app/main.py](pi/app/main.py#L46-L56) | Broadcaster reads `anchor_positions` and broadcasts via `/ws/live` | Ensure broadcaster handles DB/migration absence gracefully
| DB Schema presence (calibration_runs, fixtures, anchor_positions) | OK/TEIL | [pi/app/db/migrations/0002_phase2.sql](pi/app/db/migrations/0002_phase2.sql#L1-L20), [pi/app/api/routes_calibration.py](pi/app/api/routes_calibration.py#L1-L40) | Migrations create `calibration_runs`; anchors table handling present | Verify all expected tables (devices, settings, event_log) exist in production DB


**Top 5 Risiken (Priorität 1–5)**
- P1: Fehlender MQTT-Ingest & Topic-Definition — verhindert E2E Tracking (Impact: High)
- P2: Keine TrackingEngine — keine Positionsberechnung (Impact: High)
- P3: Kein zentraler StateManager / Guards — riskant für Live-Konfigurationen (Impact: High)
- P4: Inkonsistente DB-Tables/Schema (devices vs anchors vs anchor_positions) (Impact: Med)
- P5: UI erwartet Endpunkte, die serverseitig fehlen (tracking endpoints) (Impact: Med)


**Minimaler Fix-Plan (konkret, 6 Schritte)**
1. Definiere und dokumentiere Topic- und Payload-Schema (firmware + pi). Add README section.
2. Implementiere MQTT-Client on startup, set `app.state.mqtt_ok`, and add handlers for `range_batch` payloads (validate via pydantic).
3. Add ingestion code to upsert `devices` (first_seen_at_ms/last_seen_at_ms/role) and persist range samples or batches.
4. Implement `TrackingEngine` module (background consumer) that computes `position_cm` and writes to `latest_positions` table.
5. Add `routes_tracking.py` with `GET /api/v1/tracking/tags` and `GET /api/v1/tracking/position/{tag_mac}`.
6. Centralize system state: `app.state.system_state` and enforce guards in write endpoints (return 409 when `LIVE`).

---

Wenn du möchtest, fülle ich die Audit-Tabelle direkt in `CODEX_TASK_ANCHOR_TAG_COMPLETENESS_AUDIT.md` (überschreibe die Datei), oder ich lege stattdessen Issues/Tasks an. Welche Option bevorzugst du?