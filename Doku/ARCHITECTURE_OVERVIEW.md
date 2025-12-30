# LightTracking – Architecture Overview (1-Seite)

## Ziel
Dieses Dokument gibt neuen Mitwirkenden einen **schnellen, technischen Überblick** über Aufbau,
Datenflüsse und Verantwortlichkeiten des Systems.

---

## Systemrollen

### Raspberry Pi 5 (Base Station)
**Source of Truth**
- Persistenz: SQLite (`BaseStation.db`)
- Rechenlast: Tracking (3D Trilateration), DMX Mapping
- Orchestrierung: System States, Guards, Calibration
- Schnittstellen:
  - MQTT (Ingest + Publish)
  - REST API (FastAPI)
  - UART/RS485 (DMX)

### Anchors (Makerfabs MaUWB_ESP32S3)
- Rolle: **ANCHOR**
- Aufgaben:
  - UWB Ranging zu Tags
  - Publizieren von Range-Batches via MQTT
- Kein Wissen über Raumgeometrie oder Tracking

### Tags (Makerfabs MaUWB_ESP32S3)
- Rolle: **TAG**
- Aufgaben:
  - Teilnahme am UWB Ranging
  - Status-Telemetrie

### Moving Lights / Fixtures
- Angesteuert über DMX512
- Erhalten Pan/Tilt-Werte vom Pi

---

## Hauptkomponenten (Pi)

### MQTT Layer
- Topics:
  - `dev/+/status`
  - `dev/+/ranges`
  - `tracking/<tag>/position`
- Zweck:
  - Entkopplung von Firmware und Tracking
  - Skalierbarkeit (mehr Anchors/Tags)

### Range Cache
- Puffert letzte Distanzmessung pro (Anchor, Tag)
- Liefert zeitkonsistente Snapshots für Tracking-Ticks

### Tracking Engine
- Periodischer Tick (tracking_hz)
- Schritte:
  1. Snapshot aus RangeCache
  2. Trilateration (WLS/LM)
  3. State Evaluation (TRACKING/STALE/LOST)
  4. Publish PositionPayload

### State Manager
- Globale Systemzustände:
  - SETUP
  - CALIBRATION
  - LIVE
  - SAFE
- Erzwingt Guards (Readiness)

### DMX Engine
- Periodischer Tick (dmx_hz)
- Rechnet Zielposition → Pan/Tilt
- Slew Limiter
- Freeze bei Fehlern

---

## Datenfluss (Kurz)

```
Anchor → MQTT → RangeCache → TrackingEngine → PositionPayload
                                         ↓
                                   DMX Engine → RS485 → Fixture
```

---

## Entwurfsprinzipien
- Deterministisch
- Fail-safe (Freeze statt Bewegung)
- Source of Truth zentral
- Hardware-Unsicherheiten kapseln (AT Adapter)
- Tests vor Livebetrieb

---

## Erweiterbarkeit
- Mehr Tags (TrackingEngine skaliert)
- Weitere DMX Universes (v2)
- MQTTS / Auth (Hardening)
