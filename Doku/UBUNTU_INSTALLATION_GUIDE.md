# LightTracking – Installationsanleitung für Ubuntu / Debian PC

Diese Anleitung beschreibt die **Installation und den Betrieb von LightTracking**
auf einem **Ubuntu- oder Debian-basierten PC** als Alternative zum Raspberry Pi.

Empfohlen für:
- Live-Betrieb
- Installationen
- Entwicklungs- und Testsysteme mit höherer Stabilität

Getestete Basis:
- Ubuntu Server 22.04 LTS / 24.04 LTS
- Debian 12 (Bookworm)

---

## 1) Voraussetzungen

### Hardware
- PC oder Industrie-PC (x86_64)
- SSD empfohlen
- Ethernet-Verbindung (empfohlen)
- USB‑RS485 Adapter **mit Auto-Turnaround** (DMX)
- Makerfabs MaUWB_ESP32S3 Anchors & Tags im selben LAN

### Software
- Ubuntu Server/Desktop oder Debian
- Root- oder sudo-Zugriff
- Internetzugang für Installation

---

## 2) Betriebssystem vorbereiten

```bash
sudo apt update
sudo apt upgrade -y
sudo reboot
```

Optional (Server):
```bash
sudo timedatectl set-timezone Europe/Vienna
```

---

## 3) Systemabhängigkeiten installieren

```bash
sudo apt install -y   python3   python3-pip   python3-venv   git   sqlite3   mosquitto   mosquitto-clients   build-essential   udev
```

### MQTT Broker starten
```bash
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

Test:
```bash
mosquitto_sub -t '#' -C 1
```

---

## 4) USB‑RS485 vorbereiten (DMX)

### Adapter anschließen
```bash
ls /dev/ttyUSB*
```

Beispiel:
```
/dev/ttyUSB0
```

### Benutzerberechtigung
```bash
sudo usermod -aG dialout $USER
newgrp dialout
```

(Optional) feste Device-Regel:
```bash
sudo nano /etc/udev/rules.d/99-dmx.rules
```
```text
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", SYMLINK+="dmx"
```

```bash
sudo udevadm control --reload-rules
```

Dann:
```
/dev/dmx
```

---

## 5) Projekt installieren

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
pip install -r pi/requirements.txt
```

---

## 6) Konfiguration

### Datenbank
Standard:
```
~/LightTracking/BaseStation.db
```

Optional:
```bash
export LIGHTTRACKING_DB_PATH=/data/lighttracking/BaseStation.db
```

### MQTT
```bash
export MQTT_HOST=localhost
export MQTT_PORT=1883
```

### DMX
```bash
export DMX_UART_DEVICE=/dev/ttyUSB0
# oder /dev/dmx bei udev-Regel
```

GPIO DE/RE ist **nicht nötig**, da USB‑RS485 Auto-TX nutzt.

---

## 7) LightTracking starten (manuell)

```bash
source venv/bin/activate
uvicorn pi.app.main:app --host 0.0.0.0 --port 8000
```

Test:
```bash
curl http://localhost:8000/api/v1/state
```

---

## 8) Systemd Service (empfohlen)

```bash
sudo nano /etc/systemd/system/lighttracking.service
```

```ini
[Unit]
Description=LightTracking Service
After=network.target mosquitto.service

[Service]
User=%i
WorkingDirectory=/home/%i/LightTracking
ExecStart=/home/%i/LightTracking/venv/bin/uvicorn pi.app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Aktivieren (für aktuellen User):
```bash
sudo systemctl daemon-reload
sudo systemctl enable lighttracking@$USER
sudo systemctl start lighttracking@$USER
```

Status:
```bash
systemctl status lighttracking@$USER
```

---

## 9) Firewall (optional)

```bash
sudo ufw allow 8000/tcp
sudo ufw allow 1883/tcp
sudo ufw enable
```

---

## 10) Funktionstest

### MQTT
```bash
mosquitto_sub -t 'dev/+/status' -v
```

### API
```bash
curl http://<pc-ip>:8000/api/v1/state
```

### DMX
- Test Aim ausführen (`/api/v1/dmx/aim`)
- Fixture reagiert erwartungsgemäß

---

## 11) Unterschiede zum Raspberry Pi

| Punkt | Ubuntu/Debian PC |
|----|------------------|
| DMX | USB‑RS485 |
| GPIO | nicht nötig |
| Performance | höher |
| Stabilität | sehr hoch |
| Wartung | einfacher |

---

## 12) Empfehlung für Livebetrieb

- Ethernet statt WLAN
- USV für PC & Netzwerk
- SSD statt HDD
- Regelmäßige DB-Backups
- LIVE_CHECKLIST.md vor jeder Show durchgehen

---

## 13) Nächste Schritte

1. Anchors/Tags flashen
2. Anchor-Positionen setzen
3. Fixtures konfigurieren
4. Kalibrieren
5. LIVE_CHECKLIST.md → Go LIVE
