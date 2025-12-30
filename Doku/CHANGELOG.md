# Changelog – LightTracking

Alle relevanten Änderungen am Projekt werden in diesem Dokument festgehalten.
Das Format orientiert sich an **Keep a Changelog**.

---

## [v1.0.0] – Initial Live-Capable Release
### Added
- Raspberry Pi 5 als Base Station (Source of Truth)
- SQLite Persistenz mit Migrationen und Seeds
- MQTT Kommunikation (Status, Ranges, PositionPayloads, Cmd/Ack)
- 3D Tracking via WLS/LM Trilateration
- Tracking States: TRACKING / STALE / LOST
- Deterministische System State Machine (SETUP / CALIBRATION / LIVE / SAFE)
- Calibration Workflow mit Invalidation
- DMX512 Output (UART → RS485)
- Fixture Profiles & CRUD
- Pan/Tilt Mapping (16-bit) mit Slew Limiter und Freeze
- SIM_RANGES Modus für Entwicklung ohne UWB Hardware
- Umfassende Dokumentation (Installation, Betrieb, FMEA, Performance)

### Changed
- —

### Fixed
- —

### Removed
- —

---

## [Unreleased]
### Added
- (geplant) MQTTS
- (geplant) API Auth
- (geplant) Multi-Tag Support
- (geplant) Multi-Universe DMX

