# LightTracking – Operator UI Flow

Dieses Dokument beschreibt **den typischen Ablauf aus Sicht eines Operators**
(vor, während und nach einer Show).

---

## 1) Systemstart (Techniker)

1. Raspberry Pi einschalten
2. Service startet automatisch (`lighttracking`)
3. Anchors & Tags einschalten
4. Warten, bis Devices ONLINE sind

Operator prüft:
- System State: SETUP
- Anchors online >= Minimum
- Keine Fehler im Status

---

## 2) Raum-Setup (Einmalig / bei Änderungen)

### Anchor-Positionen
- Anchor physisch platzieren
- Positionen im UI eingeben (cm, relativ zum 0-Punkt)

### Fixtures
- Fixtures anlegen
- DMX-Adresse setzen
- Fixture-Position eintragen

---

## 3) Kalibrierung

1. Performer/Tag auf 0-Punkt stellen
2. Im UI: „Calibration starten“
3. Warten bis Result = OK
4. System bleibt in SETUP

Fehlerfall:
- Calibration FAILED → Ursachen prüfen (Anchors, Tag, Ranges)

---

## 4) Testmodus

- DMX „Aim Test“ ausführen
- Prüfen:
  - Pan/Tilt Richtung korrekt
  - Keine Ruckler
- Bei Bedarf Fixture-Offsets anpassen

---

## 5) Go LIVE

1. Operator prüft Readiness (grün)
2. Klick auf „Go LIVE“
3. System wechselt in LIVE
4. Fixtures folgen dem Performer

---

## 6) Livebetrieb

Operator beobachtet:
- Tracking State (meist TRACKING)
- Keine ERROR Events
- Bewegungen ruhig

Bei Problemen:
- Button „SAFE“ drücken
- Licht friert ein

---

## 7) Nach der Show

1. Wechsel zu SAFE
2. System stoppen oder weiterlaufen lassen
3. Optional Logs sichern

---

## 8) Notfallabläufe

### Tracking verloren
- Automatisch Freeze
- Operator entscheidet: warten oder SAFE

### Anchor fällt aus
- System ggf. weiter lauffähig (>= min)
- Sonst SAFE

---

## 9) Operator-Prinzipien
- LIVE nur bei grüner Readiness
- Bei Unsicherheit: SAFE
- Keine Anchor-Änderungen im LIVE Betrieb
