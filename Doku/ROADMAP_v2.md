# LightTracking – Roadmap v2

Diese Roadmap beschreibt **geplante Erweiterungen** über den Stand von v1.0 hinaus.
Sie ist bewusst technisch und priorisiert **Stabilität vor Feature‑Breite**.

---

## v2.0 – Sicherheit & Skalierung (hohe Priorität)

### Security / Hardening
- MQTTS (TLS) + Zertifikatsmanagement
- MQTT ACLs (Device‑spezifische Topics)
- REST API Auth (Token / Role‑based)
- Read‑only Operator Accounts

### System Robustheit
- Watchdog für Tracking & DMX Threads
- Health‑Metrics Endpoint (`/metrics`)
- Persistente Crash‑Recovery States

---

## v2.1 – Multi‑Entity Support

### Tracking
- Multi‑Tag Support
- Priorisierung / Selection Logic (Primary Tag)
- Smooth Tag Handover

### DMX
- Multi‑Universe Support
- Fixture Groups / Presets
- Szenen‑Integration

---

## v2.2 – Visualisierung & UI

- Web‑UI mit:
  - 3D Raumansicht (Anchors, Tag, Fixtures)
  - Live Tracking Visualization
  - Calibration Wizard UI
- WebSocket‑basierte Live‑Daten

---

## v2.3 – Tracking Quality

- Kalman Filter Integration
- Adaptive Outlier Rejection
- NLOS Detection Improvements
- Per‑Anchor Weight Learning

---

## v2.4 – Hardware & Deployment

- Dockerized Pi Deployment
- OTA Updates für Anchors/Tags
- Hardware Abstraction Layer (andere UWB Chips)

---

## Leitprinzipien v2
- Sicherheit vor Komfort
- Fail‑Safe vor Feature‑Tiefe
- Determinismus vor „Magic“
- Live‑Betrieb hat oberste Priorität

---

## Nicht‑Ziele
- Kein vollwertiges Lichtpult
- Keine Cloud‑Abhängigkeit
- Keine KI‑Black‑Box‑Logik im Livepfad
