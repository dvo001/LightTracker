# LightTracking – First Show Dry-Run Checklist (Generalprobe)

Diese Checkliste ist **für die allererste Show / Generalprobe** gedacht.
Ziel: das System realistisch testen – **ohne Publikum**.

---

## 1) Aufbau & Verkabelung

- [ ] Anchors montiert (finale Positionen)
- [ ] Tag funktionsfähig
- [ ] Fixtures montiert & adressiert
- [ ] RS485 / DMX sauber verkabelt
- [ ] Ethernet verbunden

---

## 2) Systemstart

- [ ] PC / Pi starten
- [ ] LightTracking Service läuft
- [ ] Mosquitto läuft
- [ ] Keine ERRORs im Log

---

## 3) Device Check

- [ ] Alle Anchors ONLINE
- [ ] Tag ONLINE
- [ ] Ranges stabil

---

## 4) Setup-Daten prüfen

- [ ] Anchor-Positionen korrekt (cm)
- [ ] Fixture-Positionen korrekt
- [ ] DMX-Adressen korrekt
- [ ] Keine Platzhalter-Werte

---

## 5) Calibration (Pflicht)

- [ ] Performer / Tag am 0-Punkt
- [ ] Calibration starten
- [ ] Result = OK
- [ ] Keine Invalidation danach

---

## 6) Tracking-Test

### Statisch
- [ ] Tag ruhig → Position stabil

### Bewegung
- [ ] Langsame Bewegung → ruhiges Follow
- [ ] Schnelle Bewegung → keine Sprünge

---

## 7) DMX-Test

- [ ] Test Aim korrekt
- [ ] Follow-Modus funktioniert
- [ ] Slew Limiter angenehm

---

## 8) Fehler-Simulation (sehr wichtig)

- [ ] Anchor kurz ausschalten → Freeze
- [ ] Tag kurz ausschalten → Freeze
- [ ] MQTT kurz trennen → Freeze
- [ ] Rückkehr stabil

---

## 9) LIVE-Probe

- [ ] Wechsel zu LIVE
- [ ] 5–10 Minuten Dauerbetrieb
- [ ] Keine ERRORs
- [ ] Operator fühlt sich sicher

---

## 10) Abschluss

- [ ] System → SAFE
- [ ] Logs prüfen
- [ ] Parameter ggf. anpassen
- [ ] Dry-Run erfolgreich

---

## Ziel
> Wenn der Dry-Run ruhig ist, ist die Show ruhig.
