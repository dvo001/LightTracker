# UI Installation (Phase-1 aligned)

1. Copy web assets:
   - templates: `pi/app/web/templates/*.html`
   - static: `pi/app/web/static/{app.js,style.css}`

2. Ensure FastAPI mounts:
   - `app.mount("/static", StaticFiles(directory=...))`
   - `Jinja2Templates(directory=...)`

3. Add UI routes (examples):
   - `/ui` -> `index.html`
   - `/ui/anchors` -> `anchors.html`
   - `/ui/fixtures` -> `fixtures.html`
   - `/ui/fixtures/new` -> `fixture_new.html`
   - `/ui/fixtures/{fixture_id}/edit` -> `fixture_edit.html`
   - `/ui/calibration` -> `calibration.html`
   - `/ui/live` -> `live.html`
   - `/ui/logs` -> `logs.html`
   - `/ui/settings` -> `settings.html`

4. Start:
   - `./start.sh`
