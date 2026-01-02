# Tracking Engine — Suggested GitHub Issues

Bitte in GitHub als Issues anlegen (Titelsemantik / Labels unten):

## 1. Implement persistent devices upsert on MQTT ingest
- Title: "tracking: upsert devices on MQTT ingest (first_seen/last_seen, role)"
- Body: "When anchor range batches arrive, ensure `devices` table is upserted with `first_seen_at_ms`, `last_seen_at_ms` and `role` ('ANCHOR'|'TAG'). This is required for online status checks and audit. Add tests and safe-create migration if table missing."
- Labels: `backend`, `db`, `enhancement`, `priority:high`

## 2. Improve solver numeric stability and performance
- Title: "tracking: improve solver numeric stability (use numpy/scipy optional)"
- Body: "Current pure-Python Gauss-Newton solver works but could be improved. Add optional numpy/scipy path for production builds; add robust outlier rejection and better initial guess strategies. Add unit tests for edge-cases."
- Labels: `backend`, `performance`, `enhancement`

## 3. Add DB indices for range_samples / latest_positions
- Title: "db: add indices for latest_positions and devices lookups"
- Body: "If persisting range samples or latest_positions, create indices on `(tag_mac, anchor_mac, ts_ms)` and ensure `devices.mac` is PK. Add migration SQL."
- Labels: `db`, `maintenance`

## 4. Expose MQTT health & metrics
- Title: "ops: expose mqtt metrics and reconnect monitoring"
- Body: "Improve MQTT client to expose connection status, reconnection attempts and event metrics via `/api/v1/health` and optionally Prometheus metrics endpoint."
- Labels: `ops`, `monitoring`

## 5. Add integration tests for end-to-end tracking
- Title: "tests: add integration tests (mosquitto + uvicorn) for E2E tracking"
- Body: "Add CI job (optional docker based) that starts a broker, runs uvicorn, publishes test range_batch messages and asserts positions returned by API."
- Labels: `tests`, `ci`, `integration`

---

If you want, I can generate GitHub issue payloads (markdown) ready to paste, or open them via GitHub API if you provide a token.