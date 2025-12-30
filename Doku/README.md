# LightTracking

**LightTracking** ist ein UWB-basiertes Echtzeit-Tracking-System zur automatischen
Steuerung von Moving Lights (DMX) auf Bühnen, Events und Installationen.

Das System verfolgt einen Performer mit einem UWB-Tag und richtet Scheinwerfer
dynamisch und sicher auf dessen Position aus.

---

## Kernmerkmale
- 🎯 3D Echtzeit-Tracking (UWB)
- 🎛️ DMX512 Steuerung von Moving Lights
- 🧠 Zentrale Logik auf Raspberry Pi 5
- 🧩 Deterministische State Machine mit Guards
- 🛑 Fail-Safe Design (Freeze / SAFE)
- 📡 MQTT-basierte Gerätekommunikation
- 🗄️ Persistenz via SQLite
- 🧪 SIM-Modus für Entwicklung ohne Hardware

---

## Systemübersicht

```
[Anchors]     [Tag]
    \         /
     \ UWB   /
      \     /
       [ Raspberry Pi 5 ]
          |  MQTT
          |  REST API
          |  Tracking + DMX
          |
       [ RS485 / DMX ]
          |
      [ Moving Lights ]
```

---

## Repository Struktur (Auszug)

```
LightTracking/
├─ pi/                 # Base Station (FastAPI, Tracking, DMX)
├─ firmware/           # Anchor / Tag Firmware (PlatformIO)
├─ CODEX_TASK_*.md     # Implementierungsphasen für Codex
├─ PI_INSTALLATION_GUIDE.md
├─ LIVE_CHECKLIST.md
├─ PERFORMANCE_TUNING_GUIDE.md
├─ FAILURE_MODES_AND_EFFECTS.md
└─ SYSTEM_TEST_PROTOCOL.md
```

---

## Schnellstart
1. Raspberry Pi vorbereiten → `PI_INSTALLATION_GUIDE.md`
2. Anchors & Tags flashen → `ANCHOR_TAG_INSTALL_GUIDE.md`
3. System starten
4. Setup → Calibration → LIVE
5. Betrieb gemäß `LIVE_CHECKLIST.md`

---

## Dokumentation (empfohlen in dieser Reihenfolge)
1. ARCHITECTURE_OVERVIEW.md
2. PI_INSTALLATION_GUIDE.md
3. INSTALL_QUICKSTART.md
4. OPERATOR_UI_FLOW.md
5. LIVE_CHECKLIST.md
6. PERFORMANCE_TUNING_GUIDE.md
7. FAILURE_MODES_AND_EFFECTS.md

---

## Entwicklungsworkflow
- Implementierung in Phasen (`CODEX_TASK_MASTER.md`)
- Review & Commit nach jeder Phase
- Tests vor Livebetrieb zwingend

---

## Lizenz / Status
- Projektstatus: **Live-fähiger Prototyp (v1.0)**
- Lizenz: TBD / intern

---

## Ziel
LightTracking wurde entwickelt, um **Bewegungslicht präzise, stabil und sicher**
mit realen Performern zu koppeln – ohne manuelles Nachführen.

