# LightTracking – Release Notes v1.0

## Release
- Version: v1.0
- Codename: Initial Live-Capable Prototype
- Target Platform: Raspberry Pi 5 + Makerfabs MaUWB_ESP32S3
- Date: TBD

---

## Highlights
- Zentrale Base Station (Pi) als Source of Truth
- 3D Tracking mittels UWB (WLS/LM Trilateration)
- Deterministische State Machine (SETUP / CALIBRATION / LIVE / SAFE)
- DMX512 Output mit Pan/Tilt 16-bit, Slew Limiter und Freeze-Fallback
- MQTT-basierte Gerätekommunikation
- Vollständige SQLite-Persistenz
- SIM_RANGES Mode für Entwicklung ohne UWB-Hardware

---

## Enthaltene Funktionen

### Infrastruktur
- FastAPI REST API (OpenAPI v1 Subset vollständig implementiert)
- Mosquitto MQTT (1883, unverschlüsselt; MQTTS vorbereitet)
- Systemd Service für stabilen Betrieb

### Devices
- Anchor Firmware (Status + Range-Batches)
- Tag Firmware (Status + Ranging Participation)
- MQTT Cmd/Ack Mechanismus

### Tracking
- Range Cache Snapshot-Fusion
- Robust WLS/LM Solver
- Zustände: TRACKING / STALE / LOST
- PositionPayload Publish via MQTT

### DMX
- Fixture Profiles & CRUD
- Mapping Zielposition → Pan/Tilt
- UART → RS485 DMX Output (Universe 1)
- Aim-Test & Freeze-Verhalten

### Calibration
- Wizard-basierter Ablauf
- Persistente Calibration Runs
- Invalidation bei Anchor-Änderungen
- LIVE-Guard erzwingt gültige Calibration

---

## Bekannte Einschränkungen (v1)
- Single DMX Universe
- Fokus auf einen Primary Tag
- MQTTS & API Auth noch nicht aktiv
- AT Command Map abhängig von Makerfabs Firmware-Version

---

## Upgrade-Hinweise
- Anchor-Positionen prüfen → ggf. neu kalibrieren
- Fixture Offsets validieren
- Performance Tuning Guide beachten

---

## Nächste Schritte (v1.x / v2)
- MQTTS + ACLs
- Multi-Tag Support
- Multi-Universe DMX
- UI Visualisierung (3D View)
