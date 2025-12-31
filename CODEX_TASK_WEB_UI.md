# CODEX_TASK_WEB_UI.md — LightTracking Webfrontend (FastAPI + Jinja2)

## Goal
Implement a lightweight Web UI (no React/Vue, no build chain) for LightTracking using:
- FastAPI (already present)
- Jinja2 templates
- Static JS/CSS (fetch against existing REST API)

UI must be served under `/ui` and include these pages:
- Dashboard: `/ui`
- Anchors: `/ui/anchors`
- Fixtures: `/ui/fixtures`, `/ui/fixtures/new`, `/ui/fixtures/{id}/edit`
- Calibration Wizard: `/ui/calibration`
- Live Monitor (read-only): `/ui/live`
- Logs: `/ui/logs`
- Settings: `/ui/settings`

## Constraints / Non-Goals
- No Node/bundler; no frontend framework.
- No authentication/authorization.
- All files UTF-8.
- Routes must not import `app.main` (avoid circular imports).
- UI may have client-side guards, but destructive actions must be guarded server-side too; if missing, add TODOs and/or server guards as appropriate.

---

## Step 1 — Dependencies
Ensure `jinja2` is installed (add to requirements or installation docs):
- `pip install jinja2`

---

## Step 2 — Create folder structure
Create:
```
pi/app/web/templates/
pi/app/web/static/
```

Create templates (UTF-8):
- `base.html`
- `index.html`
- `anchors.html`
- `fixtures.html`
- `fixture_new.html`
- `fixture_edit.html`
- `calibration.html`
- `live.html`
- `logs.html`
- `settings.html`

Create static assets:
- `style.css`
- `app.js`

---

## Step 3 — Integrate UI into FastAPI (`pi/app/main.py`)
Add:
- `StaticFiles` mount on `/static`
- `Jinja2Templates` directory
- UI routes for all `/ui*` paths listed above

Implementation pattern:
- `BASE_DIR = Path(__file__).resolve().parent`
- `templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))`
- `app.mount("/static", StaticFiles(directory=str(BASE_DIR / "web" / "static")), name="static")`

Add GET routes:
- `/ui`
- `/ui/anchors`
- `/ui/fixtures`
- `/ui/fixtures/new`
- `/ui/fixtures/{fixture_id}/edit`
- `/ui/calibration`
- `/ui/live`
- `/ui/logs`
- `/ui/settings`

Each route returns `templates.TemplateResponse("<name>.html", {"request": request, ...})`

---

## Step 4 — Base template (`base.html`)
`base.html` must include:
- Top navigation links:
  - Dashboard (`/ui`)
  - Anchors (`/ui/anchors`)
  - Fixtures (`/ui/fixtures`)
  - Calibration (`/ui/calibration`)
  - Live (`/ui/live`)
  - Logs (`/ui/logs`)
  - Settings (`/ui/settings`)
  - API Docs (`/docs`, new tab)
- Load CSS: `<link rel="stylesheet" href="/static/style.css" />`
- Load JS: `<script src="/static/app.js"></script>`

All other templates extend `base.html`.

---

## Step 5 — JS API client & page logic (`app.js`)
Create a single small client with:
- `ltFetchJson(url, opts)` → returns `{ ok, status, json }`
- `ltGetSystemState()` → `GET /api/v1/state`
- `ltAssertNotLive(actionName)` → blocks destructive actions when state is `LIVE`

### IMPORTANT: Map endpoints by reading existing code
Do NOT guess endpoints. Read and use the actual paths from:
- `pi/app/api/routes_state.py`
- `pi/app/api/routes_anchors.py`
- `pi/app/api/routes_fixtures.py`
- `pi/app/api/routes_calibration.py`
- `pi/app/api/routes_tracking.py`
- `pi/app/api/routes_events.py`
- `pi/app/api/routes_settings.py`
- `pi/app/api/routes_dmx.py` (optional button actions)

If an endpoint is missing:
- Implement UI in a safe “TODO” mode (disable button + show message)
- Add TODO comment pointing to the missing API capability
- Only add new endpoints if it is clearly intended and safe.

### Required JS functions per page
**Dashboard (`/ui`)**
- `ltRefreshDashboard()` calls `/api/v1/state` and renders key info.
- Derived warnings: mqtt down, anchors below threshold, tag stale, etc.

**Anchors (`/ui/anchors`)**
- `ltLoadAnchors()` renders table.
- Position set form: MAC, X/Y/Z (cm) required.
- Actions: enable/disable if supported by API.
- Must persist via API → SQLite.

**Fixtures (`/ui/fixtures`)**
- Render table with actions: Edit, Enable/Disable, Delete (confirm).
- Client-side guard: destructive actions blocked in LIVE.
- New page uses required fields: Name*, Profile*, Universe*, DMX Address*.
- Edit page loads fixture data and updates via actual API endpoints.

**Calibration Wizard (`/ui/calibration`)**
- Precheck: not LIVE, enough anchors online, tag chosen/online.
- Start/Abort/Status poll must use actual API endpoints.
- Show progress + result.
- Commit/discard only if API supports.

**Live Monitor (`/ui/live`)**
- Read-only.
- Poll tracking endpoint 2–5 Hz (setInterval).
- Display position/status/age/quality if provided.

**Logs (`/ui/logs`)**
- `ltLoadEvents()` calls events endpoint; render table.
- Filter by level/text if supported; otherwise client-side filter.

**Settings (`/ui/settings`)**
- Load and save settings via actual API endpoints.
- Block save in LIVE (client guard + server guard).

---

## Step 6 — Required fields marking
In templates (New/Edit fixture, anchor position), mark required fields with:
- Visible asterisk `<span class="req">*</span>`
- HTML `required` attribute

Add to `style.css`:
- `.req { color: #ff6b6b; font-weight: 700; }`

---

## Step 7 — Minimal technical styling (`style.css`)
Provide:
- Basic layout, cards, tables, buttons
- Responsive (mobile-friendly)
- No external dependencies

---

## Step 8 — Safety (client + server)
Client-side:
- Use `ltAssertNotLive()` to block destructive actions in LIVE.

Server-side:
- Ensure destructive endpoints are guarded in LIVE:
  - Changing anchors positions
  - Creating/updating/deleting fixtures
  - Starting calibration
  - Changing settings
If not implemented, add TODOs and/or implement guards.

---

## Step 9 — Acceptance Criteria (Done)
UI is complete when:
1. `GET /ui` renders (HTTP 200) with no template errors.
2. `/static/style.css` and `/static/app.js` load (HTTP 200).
3. All UI routes return HTTP 200:
   - `/ui`, `/ui/anchors`, `/ui/fixtures`, `/ui/fixtures/new`, `/ui/fixtures/{id}/edit`, `/ui/calibration`, `/ui/live`, `/ui/logs`, `/ui/settings`
4. Dashboard displays `/api/v1/state` data.
5. Fixtures: list + create + edit + delete/disable/enable work using actual API endpoints, or are clearly TODO with disabled controls.
6. Anchors: list works; position set works or TODO.
7. Calibration: wizard can start/abort/status using actual API endpoints, or TODO.
8. Live monitor shows tracking data from actual endpoint, or TODO.
9. Logs show events from actual endpoint.
10. Settings load/save using actual endpoints, blocked in LIVE.

---

## Step 10 — README update (optional but recommended)
Add a short section:
- Start:
  - `export PYTHONPATH=$PWD/pi`
  - `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- UI:
  - `http://<host>:8000/ui`
