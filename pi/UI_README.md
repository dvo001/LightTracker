# LightTracker PI — Web UI Quickstart

Install dependencies (from project root):

```powershell
C:/path/to/venv/Scripts/python.exe -m pip install -r pi/requirements.txt
```

Start the API (from `pi`):

```powershell
cd pi
C:/path/to/venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open the Web UI:

- Dashboard: http://localhost:8000/ui
- API Docs: http://localhost:8000/docs

Notes:
- The app uses MQTT; run a broker for full functionality.
- Static files are served under `/static` and templates under `pi/app/web/templates`.
