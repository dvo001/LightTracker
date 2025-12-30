# LightTracking – System Test Protocol (Abnahmeprotokoll)

Dieses Dokument dient als **formales Abnahme- und Testprotokoll**
für LightTracking vor dem Liveeinsatz.

---

## Projekt
- Name: LightTracking
- Version: v1.0
- Ort / Bühne:
- Datum:
- Verantwortlich:

---

## 1) Systemumgebung

### Hardware
- [ ] Raspberry Pi 5
- [ ] Anchors (Anzahl): ______
- [ ] Tags (Anzahl): ______
- [ ] Fixtures (Anzahl): ______
- [ ] RS485 Interface geprüft

### Software
- [ ] Raspberry Pi OS 64-bit
- [ ] LightTracking Service installiert
- [ ] Mosquitto läuft

---

## 2) Installationstest

- [ ] Service startet automatisch
- [ ] API erreichbar (`/api/v1/state`)
- [ ] Migrationen erfolgreich
- [ ] Keine ERRORs im event_log

---

## 3) Device Tests

### Anchors
- [ ] Alle Anchors ONLINE
- [ ] Statusmeldungen periodisch
- [ ] Ranges empfangen

### Tags
- [ ] Tag ONLINE
- [ ] Ranges zu Tag vorhanden

---

## 4) Tracking Tests

### Statisch
- [ ] Tag ruhig → Position stabil
- [ ] resid_m im Erwartungsbereich

### Dynamisch
- [ ] Langsame Bewegung → flüssiges Follow
- [ ] Schnelle Bewegung → keine Sprünge

### Fehlerfälle
- [ ] Anchor kurz OFFLINE → System stabil
- [ ] Tag kurz OFFLINE → Freeze

---

## 5) Calibration Tests

- [ ] Calibration Start erfolgreich
- [ ] Calibration Result = OK
- [ ] Calibration invalidiert bei Anchor-Änderung
- [ ] LIVE ohne Calibration geblockt

---

## 6) DMX Tests

### Test Aim
- [ ] Aim Test bewegt Fixtures korrekt
- [ ] Stop beendet Bewegung

### LIVE Follow
- [ ] Follow in LIVE aktiv
- [ ] Freeze bei STALE/LOST
- [ ] SAFE stoppt Bewegung sofort

---

## 7) State Machine

- [ ] SETUP → CALIBRATION korrekt
- [ ] SETUP → LIVE nur bei Readiness
- [ ] LIVE → SAFE jederzeit möglich

---

## 8) Performance

- [ ] CPU Last stabil
- [ ] Keine Latenzspitzen
- [ ] tracking_hz / dmx_hz akzeptabel

---

## 9) Abschlussbewertung

### Ergebnis
- [ ] System freigegeben für LIVE
- [ ] System nicht freigegeben (Begründung):

### Unterschrift
Name / Rolle:
Datum:
