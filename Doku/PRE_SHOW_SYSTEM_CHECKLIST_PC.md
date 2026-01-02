# LightTracking – Pre-Show System Checklist (PC / Ubuntu)

Diese Checkliste ist **unmittelbar vor einer Show** durchzugehen.
Sie richtet sich an **Technik / Operator** und ist für **Ubuntu Server/Desktop PCs** gedacht.

Ziel: maximale Stabilität, keine Überraschungen während LIVE.

---

## 0) Zeitpunkt
⏱️ Empfohlen: **30–60 Minuten vor Showbeginn**  
⛔ Nach Abschluss: **keine Änderungen mehr am System**

---

## 1) Systemzustand (PC)

### Hardware
- [ ] PC steht stabil, keine losen Kabel
- [ ] Ethernet verbunden (kein WLAN für Live)
- [ ] USB-RS485 Adapter fest verbunden
- [ ] USV aktiv (falls vorhanden)

### Betriebssystem
```bash
uptime
```
- [ ] System läuft >10 Minuten stabil
- [ ] Keine Reboots geplant

```bash
free -h
df -h
```
- [ ] Genügend RAM frei
- [ ] ≥20 % freier Speicher

---

## 2) Services

### Mosquitto (MQTT)
```bash
systemctl status mosquitto
```
- [ ] Status: active (running)

### LightTracking
```bash
systemctl status lighttracking@$USER
```
- [ ] Status: active (running)
- [ ] Keine ERROR-Spikes im Journal:
```bash
journalctl -u lighttracking@$USER -n 50
```

---

## 3) Netzwerk & MQTT

### Broker erreichbar
```bash
mosquitto_sub -t 'dev/+/status' -C 1
```
- [ ] Statusnachricht empfangen

### Anchors & Tag
- [ ] Alle Anchors ONLINE
- [ ] Mindestens `min_anchors_online` erfüllt
- [ ] Tag ONLINE

⚠️ Wenn nicht:
- Anchors neu starten
- LAN prüfen
- **nicht LIVE gehen**

---

## 4) API & System State

```bash
curl http://localhost:8000/api/v1/state
```

- [ ] API erreichbar
- [ ] System State: SETUP
- [ ] Readiness Gates grün (bis auf LIVE)

---

## 5) Datenbank & Persistenz

- [ ] `BaseStation.db` vorhanden
- [ ] Keine DB-Fehler im Log
- [ ] Letzte Calibration vorhanden

(Optional Backup):
```bash
cp BaseStation.db BaseStation.db.bak.$(date +%s)
```

---

## 6) Calibration Check

- [ ] Anchor-Positionen final
- [ ] Calibration Result = OK
- [ ] Calibration nicht invalidiert
- [ ] Kein Anchor seitdem verändert

Wenn unsicher:
➡️ **Calibration neu durchführen**

---

## 7) DMX / Output

### Interface
```bash
ls -l /dev/ttyUSB*
```
oder:
```bash
ls -l /dev/dmx
```
- [ ] DMX Device vorhanden

### Test Aim
- [ ] Test Aim ausführen
- [ ] Fixtures bewegen sich korrekt
- [ ] Stop funktioniert sofort

⚠️ Keine Ruckler / keine ungewollten Bewegungen

---

## 8) Performance Snapshot

```bash
htop
```
- [ ] CPU Load stabil
- [ ] Kein Prozess >70 % dauerhaft

Empfehlung:
- tracking_hz ≤ 20
- dmx_hz ≤ 30

---

## 9) Sicherheitsprüfung (kritisch)

- [ ] SAFE Button / API bekannt
- [ ] Operator weiß:
  - wie SAFE ausgelöst wird
  - dass bei Unsicherheit SAFE genutzt wird
- [ ] Keine Anchor-Position-Änderungen im LIVE

---

## 10) Go / No-Go Entscheidung

### GO (alle erfüllt)
- [ ] Alle Devices ONLINE
- [ ] Calibration gültig
- [ ] Test Aim ok
- [ ] Keine Errors

➡️ **LIVE freigeben**

```bash
curl -X POST http://localhost:8000/api/v1/state   -H 'Content-Type: application/json'   -d '{"target_state":"LIVE"}'
```

### NO-GO (irgendein Punkt offen)
- [ ] Ursache klären
- [ ] Nicht LIVE gehen

---

## 11) Während der Show (Kurz)

- [ ] Tracking State meist TRACKING
- [ ] Keine ERROR-Spikes
- [ ] Bei Problemen: SAFE

---

## 12) Nach der Show

- [ ] System → SAFE
- [ ] Logs sichern (optional)
- [ ] System sauber herunterfahren

```bash
sudo shutdown -h now
```

---

## Grundprinzip
> **Im Zweifel: SAFE.**  
> Keine Bewegung ist besser als falsche Bewegung.
