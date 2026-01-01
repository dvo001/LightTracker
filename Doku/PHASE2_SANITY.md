# Phase-2 Sanity Checks

This document lists quick sanity checks to run after deploying Phase-2 changes.

1) Start the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

2) Run smoke tests (Linux/macOS)

```bash
./tests/smoke_tests.sh
```

3) On Windows (PowerShell)

```powershell
.\tests\smoke_tests.ps1
```

4) Check systemd unit (example)

Copy `deploy/lighttracking.env` to `/etc/lighttracking.env` and adjust `LT_DB_PATH` then:

```bash
sudo cp deploy/lighttracking.env /etc/lighttracking.env
sudo cp deploy/lighttracking.service /etc/systemd/system/lighttracking.service
sudo systemctl daemon-reload
sudo systemctl enable --now lighttracking.service
sudo journalctl -u lighttracking -f
```

5) DB migration check

```bash
sqlite3 /var/lib/lighttracking/lighttracker.db "SELECT id, applied_at_ms FROM schema_migrations ORDER BY id;"
```
