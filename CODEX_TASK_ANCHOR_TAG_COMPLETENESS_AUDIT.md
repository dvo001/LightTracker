```markdown
```
---
## Zeilen-genaue Belege (Deep Audit)
Nachfolgend zeige ich pro Audit-Checkpunkt die relevanten Dateien mit Zeilenangaben, die meine Bewertungen stützen.
- MAC als Primär-ID: [pi/app/api/routes_anchors.py](pi/app/api/routes_anchors.py#L22-L22), [pi/app/api/routes_anchors.py](pi/app/api/routes_anchors.py#L48-L65)
- Pi als Source-of-Truth (SQLite & Migrations): [pi/app/db/__init__.py](pi/app/db/__init__.py#L1-L20), [pi/app/db/migrations/runner.py](pi/app/db/migrations/runner.py#L1-L30), [pi/app/db/migrations/0002_phase2.sql](pi/app/db/migrations/0002_phase2.sql#L1-L20)
- System State / Guards (fehlt zentral): [pi/app/api/routes_state.py](pi/app/api/routes_state.py#L1-L40) (statisches `system_state: 'SETUP'`)
- MQTT-Status sichtbar in UI / Health, aber kein Subscriber: UI & client expectations: [pi/app/web/static/app.js](pi/app/web/static/app.js#L84-L92), [pi/UI_README.md](pi/UI_README.md#L22); health reads `app.state.mqtt_ok`: [pi/app/api/routes_health.py](pi/app/api/routes_health.py#L20-L30)
- Topic-/Payload-Definition (nicht gefunden): keine zentrale Topic-Definition im Pi-Code; UI expects tracking endpoints: [pi/app/web/static/app.js](pi/app/web/static/app.js#L18-L19)
- Payload-Validation (fehlend): keine Range/Batch pydantic-Modelle oder handlers im `pi/app` — check API router list: [pi/app/api/__init__.py](pi/app/api/__init__.py#L1-L10)
- Devices / Online status (partial): anchors API reads `last_seen_at_ms` from `anchor_positions` or `anchors` table: [pi/app/api/routes_anchors.py](pi/app/api/routes_anchors.py#L20-L34), UI references anchor listing: [pi/app/web/static/app.js](pi/app/web/static/app.js#L128-L137)
- Anchor position write API: `POST /api/v1/anchors/position` implemented: [pi/app/api/routes_anchors.py](pi/app/api/routes_anchors.py#L64-L71) — missing LIVE-guard (see `routes_state`)
- Tracking endpoints expected by UI but missing server-side: [pi/app/web/static/app.js](pi/app/web/static/app.js#L18-L19) vs. included API routers: [pi/app/api/__init__.py](pi/app/api/__init__.py#L1-L10) (no `routes_tracking`)
- Broadcaster & websocket anchor_pos broadcast (shows anchor_positions usage): [pi/app/main.py](pi/app/main.py#L46-L56)
- DB connection and configurable path (`LT_DB_PATH`): [pi/app/db/__init__.py](pi/app/db/__init__.py#L1-L12)

Diese Belege liefern die Grundlage für die Bewertungen in Abschnitt "Audit — erste Befunde". Möchtest du, dass ich jetzt

1) die Tabelle aus Abschnitt 3 komplettiere (jedes Checkfeld mit Status + Datei:Zeilen + Fix-Vorschlag), oder
2) direkt Issues/Task-Items mit konkreten Implementationsschritten vorbereite (nur Dokumentation, keine Code-Änderungen)?

---
# CODEX_TASK_ANCHOR_TAG_COMPLETENESS_AUDIT.md
Repo: **LightTracking**  
Ziel: **Audit** der Anchor- und Tag-Implementierung auf Vollständigkeit (ohne Code-Änderungen).  
Output: strukturierte Befundliste + konkrete Fix-Empfehlungen.

---

## 0) Regeln (wichtig)
- **Nur Analyse**, keine Refactors, keine neuen Features, keine Code-Änderungen.
- **Keine Annahmen** außerhalb des Repos: bewerte nur, was im Code tatsächlich vorhanden ist.
- Nutze **Datei + Zeilenangaben** bei jedem Befund.
- Prüfe besonders auf:
  - zirkuläre Imports
  - falsche/inkonsistente MAC-Handhabung
  - fehlende MQTT Topic-Subscriptions
  - fehlende Persistenz/Schema-Mismatches
  - Gate/State-Guards (SETUP/SAFE/LIVE)

---

## 1) Audit-Checkliste (Soll vs Ist)
### 1.1 Systemweite Invarianten
*** End Patch
