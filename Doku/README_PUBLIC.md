# LightTracking

LightTracking ist ein **UWB-basiertes Echtzeit-Tracking-System** zur automatischen
Steuerung von Moving Lights (DMX) bei Bühnenproduktionen, Events und Installationen.

Ein Performer trägt einen UWB-Tag, dessen Position in Echtzeit erfasst wird.
Eine zentrale Base Station richtet Scheinwerfer präzise, ruhig und sicher auf diese Position aus.

---

## Features
- 🎯 **3D Echtzeit-Tracking** (UWB)
- 🎛️ **DMX512 Steuerung** von Moving Lights (Pan/Tilt 16‑bit)
- 🧠 **Zentrale Logik** auf Raspberry Pi
- 🛑 **Fail‑Safe Design** (Freeze / SAFE)
- 📡 **MQTT Kommunikation**
- 🗄️ **SQLite Persistenz**
- 🧪 **SIM‑Modus** für Entwicklung ohne Hardware

---

## Architektur (Kurzüberblick)

```
[ UWB Anchors ]     [ UWB Tag ]
        \             /
         \           /
          \         /
         [ Raspberry Pi ]
            |  Tracking
            |  DMX Logic
            |  REST API
            |
         [ DMX / RS485 ]
            |
       [ Moving Lights ]
```

- **Anchors & Tag**: liefern Distanzdaten
- **Base Station**: berechnet Position & steuert Licht
- **DMX**: Ausgabe an professionelle Scheinwerfer

---

## Typische Einsatzszenarien
- Follow‑Spot‑Ersatz
- Interaktive Bühnenbeleuchtung
- Tanz‑ & Theaterproduktionen
- Installationen mit bewegtem Licht

---

## Projektstatus
- Status: **Live‑fähiger Prototyp (v1.0)**
- Fokus: Stabilität, Sicherheit, Nachvollziehbarkeit
- Erweiterungen geplant (siehe Roadmap)

---

## Hardware (Beispiel)
- Raspberry Pi 5
- Makerfabs MaUWB_ESP32S3 (Anchors & Tag)
- DMX‑fähige Moving Lights

---

## Dokumentation
- Installation & Betrieb: siehe interne Docs
- Architektur & Sicherheit: intern verfügbar

---

## Hinweis
Dieses Repository enthält sowohl Entwicklungs‑ als auch Betriebsartefakte.
Einige Dokumente sind für den professionellen Live‑Betrieb gedacht.

