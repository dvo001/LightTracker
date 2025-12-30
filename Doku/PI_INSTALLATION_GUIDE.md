# LightTracking – Installationsanleitung Raspberry Pi 5

Diese Anleitung beschreibt die **vollständige Installation und Inbetriebnahme** von LightTracking
auf einem **Raspberry Pi 5** (empfohlen: Raspberry Pi OS 64-bit).

Zielgruppe: technisch versierte Anwender / Entwickler / Operatoren.

---

## 1) Voraussetzungen

### Hardware
- Raspberry Pi 5 (empfohlen 4 GB oder 8 GB RAM)
- microSD oder NVMe SSD (≥16 GB empfohlen)
- Netzwerk (Ethernet bevorzugt, WLAN möglich)
- RS485 Transceiver (z. B. MAX485) für DMX
- Optional: GPIO-Leitung für DE/RE Steuerung
- Makerfabs MaUWB_ESP32S3 Anchors/Tags im gleichen LAN

### Software
- Raspberry Pi OS (64-bit)
- Internetzugang für Installation (später optional offline)

---

## 2) Raspberry Pi OS vorbereiten

### OS Installation
1. Raspberry Pi Imager verwenden
2. OS auswählen: **Raspberry Pi OS (64-bit)**
3. Optional:
   - SSH aktivieren
   - Hostname setzen (z. B. `basestation`)
   - WLAN konfigurieren (falls kein Ethernet)

### Erststart
```bash
sudo apt update
sudo apt upgrade -y
sudo reboot
```

---

## 3) Systemabhängigkeiten installieren

```bash
sudo apt install -y   python3   python3-pip   python3-venv   git   sqlite3   mosquitto   mosquitto-clients   build-essential
```

### Mosquitto aktivieren
```bash
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```
Standardmäßig lauscht Mosquitto auf **Port 1883** im lokalen Netz.

---

## 4) Projekt installieren

### Repository klonen
```bash
cd ~
git clone <DEIN_REPO_URL> LightTracking
cd LightTracking
```

### Python Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

### Python Dependencies installieren
```bash
pip install -r pi/requirements.txt
```

---

## 5) Konfiguration

### Datenbank
Die SQLite-Datenbank wird **automatisch beim ersten Start** erzeugt.

Standardpfad (empfohlen):
```
~/LightTracking/BaseStation.db
```

Optional per Environment Variable:
```bash
export LIGHTTRACKING_DB_PATH=/pfad/zur/BaseStation.db
```

### MQTT
Standardannahmen:
- Broker: `localhost`
- Port: `1883`

Optional per Environment:
```bash
export MQTT_HOST=localhost
export MQTT_PORT=1883
```

### DMX / RS485
Standard:
- UART Device: `/dev/serial0`
- Baudrate: 250000, 8N2

Optional (falls DE/RE per GPIO):
```bash
export DMX_RS485_DE_GPIO=18
```

⚠️ Stelle sicher:
- UART ist aktiviert (`raspi-config` → Interface → Serial)
- Keine Login-Shell auf Serial

---

## 6) LightTracking starten (manuell)

```bash
cd ~/LightTracking
source venv/bin/activate
uvicorn pi.app.main:app --host 0.0.0.0 --port 8000
```

### Erwartetes Verhalten
- Migrationen laufen automatisch
- API erreichbar unter:
  - http://<pi-ip>:8000/api/v1/state
- MQTT verbindet sich mit Broker
- event_log wird gefüllt

---

## 7) Systemd Service (empfohlen für Betrieb)

### Service-Datei erstellen
```bash
sudo nano /etc/systemd/system/lighttracking.service
```

Inhalt:
```ini
[Unit]
Description=LightTracking Service
After=network.target mosquitto.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/LightTracking
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/pi/LightTracking/venv/bin/uvicorn pi.app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### Service aktivieren
```bash
sudo systemctl daemon-reload
sudo systemctl enable lighttracking
sudo systemctl start lighttracking
```

### Status prüfen
```bash
sudo systemctl status lighttracking
journalctl -u lighttracking -f
```

---

## 8) Firewall (optional, empfohlen)

```bash
sudo apt install -y ufw
sudo ufw allow 8000/tcp
sudo ufw allow 1883/tcp
sudo ufw enable
```

---

## 9) Erster Funktionstest

### API
```bash
curl http://localhost:8000/api/v1/state
```

### MQTT
```bash
mosquitto_sub -t 'dev/+/status' -v
```

Beim Einschalten eines Anchors sollte ein Status erscheinen.

---

## 10) Typische Fehler & Troubleshooting

### API startet nicht
- `pip install -r pi/requirements.txt` erneut prüfen
- `journalctl -u lighttracking` lesen

### MQTT verbindet nicht
- `mosquitto` läuft?
- Port 1883 frei?
- `MQTT_HOST` korrekt?

### DMX funktioniert nicht
- UART aktiviert?
- `/dev/serial0` vorhanden?
- GND gemeinsam mit RS485 Transceiver?
- Kein anderes Programm blockiert UART?

### Performance
- CPU-Last prüfen (`htop`)
- tracking_hz / dmx_hz ggf. reduzieren

---

## 11) Nächste Schritte

1. Anchors & Tags einschalten
2. Anchor-Positionen setzen (`/api/v1/anchors`)
3. Fixtures konfigurieren
4. Kalibrieren
5. LIVE_CHECKLIST.md durchgehen
6. Go LIVE 🚀

---

## 12) Sicherheit (Ausblick)
- MQTTS (TLS)
- API Auth
- Read-only UI für Operatoren
- Separate VLANs

