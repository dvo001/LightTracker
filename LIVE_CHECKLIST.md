# LightTracking – LIVE CHECKLIST (Preflight für Bühnenbetrieb)

Diese Checkliste ist für den Übergang von SETUP/CALIBRATION nach LIVE gedacht.
Sie ist in **Preflight**, **Go/No-Go**, **Live Monitoring** und **Post-Live** gegliedert.

---

## 1) Preflight – Infrastruktur

### Netzwerk
- [ ] Isoliertes LAN aktiv (Pi + Anchors + Tags im selben Netz)
- [ ] Broker erreichbar (`mosquitto_sub -h <pi-ip> -t '#' -C 1` oder equivalent)
- [ ] mDNS (optional) aufgelöst: `basestation.local` → Pi IP
- [ ] Keine Doppel-IP/ARP Konflikte (optional `arp -a` prüfen)

### Raspberry Pi 5 System
- [ ] Zeit korrekt (NTP), `date` plausibel
- [ ] CPU/RAM ausreichend (keine Swap-Stürme)
- [ ] Dienst startet sauber (systemd oder manual)
- [ ] DB WAL aktiv (journal_mode=WAL)

### Storage / DB Hygiene
- [ ] `BaseStation.db` vorhanden und beschreibbar
- [ ] Freier Speicher ausreichend (Logs)
- [ ] Optional: Retention Tasks konfiguriert (event_log, position_log)

---

## 2) Preflight – Devices & Readiness

### Anchors
- [ ] Mindestens `guards.min_anchors_online` Anchors ONLINE (default 4)
- [ ] Keine STALE/OFFLINE Devices im kritischen Set
- [ ] Jeder ONLINE Anchor hat **Position** gesetzt (anchor_positions vollständig)
- [ ] Anchor Positions plausibel (cm, erwarteter Raum, keine Tippfehler)

### Tag(s)
- [ ] Mindestens 1 Tag ONLINE
- [ ] Selected “primary tag” klar (falls UI/Setting vorhanden)
- [ ] Tag steht für Calibration/Start am 0-Punkt bereit

### MQTT Telemetrie
- [ ] `dev/+/status` kommt periodisch (default 5s)
- [ ] `dev/+/ranges` kommt für den Tag (bei SIM/real)
- [ ] Keine massiven parse_errors/counters (im status/counters oder event_log)

---

## 3) Preflight – Calibration

### Preconditions
- [ ] System State ist SETUP
- [ ] DMX Testmodus aktiv? Falls ja: bewusst / unter Kontrolle
- [ ] Anchor Layout final (keine geplanten Änderungen während Calibration)

### Calibration Run
- [ ] Calibration gestartet via API `/api/v1/calibration/start`
- [ ] Run endet mit `result=OK`
- [ ] `calibration_runs.invalidated_at_ms` ist NULL (nicht invalidiert)
- [ ] (Optional) summary_json enthält plausible Werte (resid, anchors_used)

### Invalidation
- [ ] Keine Anchor-Position Updates nach Calibration (sonst neu kalibrieren)

---

## 4) Preflight – Fixtures & DMX

### Fixtures Setup
- [ ] Mindestens 1 Fixture enabled
- [ ] Fixture Profile korrekt (`generic_mh_16bit_v1` oder real)
- [ ] DMX Base Address korrekt und kollisionsfrei
- [ ] Fixture Positionen korrekt (cm)

### DMX Driver
- [ ] UART Device korrekt (`dmx.uart_device`, z.B. `/dev/serial0`)
- [ ] RS485 Transceiver korrekt verkabelt (GND gemeinsam)
- [ ] Optional: DE/RE GPIO korrekt (falls genutzt)
- [ ] DMX Test Aim in SETUP funktioniert:
  - [ ] `/api/v1/dmx/aim` bewegt Fixtures erwartungsgemäß
  - [ ] `/api/v1/dmx/stop` stoppt zuverlässig

### Safety Behavior
- [ ] Freeze Verhalten bestätigt:
  - [ ] Wenn Tracking STALE/LOST → keine unkontrollierte Bewegung
  - [ ] Wenn system.state != LIVE → keine DMX-Updates

---

## 5) Go/No-Go Entscheidung

### Go Kriterien (alle müssen erfüllt sein)
- [ ] Readiness Gates OK (API `/api/v1/state` zeigt Gates ok)
- [ ] Gültige Calibration für primary tag vorhanden
- [ ] Tracking liefert stabile PositionPayloads (ohne Sprünge)
- [ ] DMX Test Aim stabil, keine UART Fehler im event_log
- [ ] Operator kennt SAFE Notfallpfad

### No-Go / Stop Kriterien (irgendeines erfüllt)
- [ ] Anchors < min online
- [ ] Anchor position missing
- [ ] Calibration invalid/failed/missing
- [ ] DMX Driver Fehler wiederholt
- [ ] Tracking LOST/unstabil (Sprünge > toleranz) ohne Ursache

---

## 6) Transition to LIVE

- [ ] `POST /api/v1/state { "target_state": "LIVE" }` erfolgreich
- [ ] System bestätigt LIVE und startet DMX Follow
- [ ] Beobachtung: 30s Stabilitätsfenster ohne Anomalie

---

## 7) Live Monitoring (während Betrieb)

### Technische Indikatoren
- [ ] Event log keine ERROR-Spikes
- [ ] MQTT reconnect counters bleiben niedrig
- [ ] Tracking state überwiegend TRACKING (STALE nur kurz, LOST selten)
- [ ] resid_m im erwarteten Bereich (baseline definieren)
- [ ] anchors_used stabil (z.B. >=4)

### Operator Actions
- [ ] Bei drift/unstabil: Wechsel zu SAFE
- [ ] Bei DMX Anomalie: `/api/v1/dmx/stop` (wenn implementiert) und SAFE
- [ ] Bei Anchor outage: Entscheidung SAFE vs weiter mit reduziertem Set (Policy)

---

## 8) SAFE / Notfallprozedur

- [ ] `POST /api/v1/state { "target_state": "SAFE" }`
- [ ] DMX Freeze / Safe Scene aktiv (je nach Implementierung)
- [ ] Root cause in event_log nachvollziehbar

---

## 9) Post-Live

- [ ] Export event_log (Zeitraum) für Analyse
- [ ] Optional: position_log export für Playback/Debug
- [ ] Notiere Raumänderungen (Anchor/Fix positions) für nächste Session
- [ ] Backup `BaseStation.db`

---

## 10) Quick Commands (optional)
- API State: `curl http://<pi-ip>/api/v1/state`
- Start Calibration: `curl -X POST http://<pi-ip>/api/v1/calibration/start -H 'Content-Type: application/json' -d '{"tag_mac":"..","duration_ms":6000}'`
- Go LIVE: `curl -X POST http://<pi-ip>/api/v1/state -H 'Content-Type: application/json' -d '{"target_state":"LIVE"}'`
