# LightTracking - Installationsanleitung Ubuntu Server (Installation in /opt)

Diese Anleitung beschreibt die Installation und den Betrieb von LightTracking
auf einem Ubuntu Server. Das Installationsverzeichnis ist **/opt/lighttracking**.

Getestete Basis:
- Ubuntu Server 22.04 LTS / 24.04 LTS

---

## 1) Voraussetzungen

### Hardware
- x86_64 Server/PC
- SSD empfohlen
- Ethernet-Verbindung (empfohlen)
- USB-RS485 Adapter mit Auto-Turnaround (DMX)
- Makerfabs MaUWB_ESP32S3 Anchors & Tags im selben LAN

### Software
- Ubuntu Server
- Root- oder sudo-Zugriff
- Internetzugang fuer die Installation

---

## 2) System vorbereiten

```bash
sudo apt update
sudo apt upgrade -y
sudo reboot
```

Optional (Zeitzone):
```bash
sudo timedatectl set-timezone Europe/Vienna
```

---

## 3) Systempakete installieren

```bash
sudo apt install -y \
  python3 \
  python3-pip \
  python3-venv \
  git \
  sqlite3 \
  mosquitto \
  mosquitto-clients \
  build-essential \
  udev
```

### MQTT Broker aktivieren
```bash
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

Test:
```bash
mosquitto_sub -t '#' -C 1
```

---

## 4) Service-User und Verzeichnisse

```bash
sudo useradd --system --home /opt/lighttracking --shell /usr/sbin/nologin --user-group --no-create-home lighttrack
sudo mkdir -p /opt/lighttracking
sudo chown -R lighttrack:lighttrack /opt/lighttracking
```

DMX/RS485 Zugriffsrechte:
```bash
sudo usermod -aG dialout lighttrack
```

Optional (feste Device-Regel):
```bash
sudo nano /etc/udev/rules.d/99-dmx.rules
```
```text
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", SYMLINK+="dmx"
```
```bash
sudo udevadm control --reload-rules
```
Dann steht das Geraet als `/dev/dmx` zur Verfuegung.

---

## 5) Projekt installieren (in /opt)

Es gibt zwei Varianten:

### Variante A: Vollstaendiges Repo (inkl. Firmware-Quellen)
```bash
sudo -u lighttrack -H git clone https://github.com/dvo001/LightTracker /opt/lighttracking
```

### Variante B: Server-only (ohne Firmware/Docs/Tests)
Diese Variante laedt nur die fuer den Serverbetrieb noetigen Ordner (`app`, `pi`, `deploy`).
```bash
sudo -u lighttrack -H git clone --filter=blob:none --sparse https://github.com/dvo001/LightTracker /opt/lighttracking
sudo -u lighttrack -H git -C /opt/lighttracking sparse-checkout set app pi deploy
```

### Gemeinsame Schritte
```bash
sudo -u lighttrack -H python3 -m venv /opt/lighttracking/venv
sudo -u lighttrack -H /opt/lighttracking/venv/bin/pip install --upgrade pip
sudo -u lighttrack -H /opt/lighttracking/venv/bin/pip install -r /opt/lighttracking/pi/requirements.txt
```

---

## 6) Konfiguration

### Datenbank
```bash
sudo mkdir -p /opt/lighttracking/pi/app/data
sudo chown -R lighttrack:lighttrack /opt/lighttracking/pi/app/data
```

### Environment-Datei
```bash
sudo tee /etc/lighttracking.env > /dev/null <<'EOF'
LT_DB_PATH=/opt/lighttracking/pi/app/data/lighttracker.db
MQTT_HOST=localhost
MQTT_PORT=1883
PORT=8000
EOF
```

### DMX Device
Standard-Device ist `/dev/serial0`. Fuer USB-RS485 auf Servern ist meist
`/dev/ttyUSB0` oder `/dev/dmx` korrekt. Die Einstellung erfolgt ueber die API:

```bash
curl -X PUT http://localhost:8000/api/v1/dmx/config \
  -H 'Content-Type: application/json' \
  -d '{"mode":"uart","uart_device":"/dev/ttyUSB0"}'
```

---

## 7) LightTracking starten (manuell)

```bash
sudo -u lighttrack -H bash -c 'set -a; source /etc/lighttracking.env; set +a; /opt/lighttracking/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$PORT"'
```

Test:
```bash
curl http://localhost:8000/api/v1/state
```

---

## 8) Systemd Service (empfohlen)

```bash
sudo tee /etc/systemd/system/lighttracking.service > /dev/null <<'EOF'
[Unit]
Description=LightTracking Service
After=network.target mosquitto.service

[Service]
Type=simple
User=lighttrack
Group=lighttrack
EnvironmentFile=/etc/lighttracking.env
Environment=PYTHONUNBUFFERED=1
WorkingDirectory=/opt/lighttracking
ExecStart=/opt/lighttracking/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lighttracking
```

Status:
```bash
systemctl status lighttracking
journalctl -u lighttracking -f
```

---

## 9) HTTPS auf Port 443 (Reverse-Proxy, self-signed)

Empfohlen: Uvicorn bleibt auf `PORT=8000`, Nginx terminiert TLS auf 443.

### Nginx installieren
```bash
sudo apt install -y nginx
```

### Self-signed Zertifikat erzeugen
```bash
sudo mkdir -p /etc/lighttracking/certs
sudo openssl req -x509 -nodes -newkey rsa:4096 \
  -keyout /etc/lighttracking/certs/lighttracking.key \
  -out /etc/lighttracking/certs/lighttracking.crt \
  -days 825 -subj "/CN=lighttracking.local"
```

### Nginx Config aktivieren
```bash
sudo cp /opt/lighttracking/deploy/lighttracking.nginx.conf /etc/nginx/sites-available/lighttracking
sudo ln -sf /etc/nginx/sites-available/lighttracking /etc/nginx/sites-enabled/lighttracking
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Test (self-signed, daher -k):
```bash
curl -k https://localhost/api/v1/state
```

---

## 10) Firewall (optional)

```bash
sudo apt install -y ufw
sudo ufw allow 8000/tcp
sudo ufw allow 443/tcp
sudo ufw allow 1883/tcp
sudo ufw enable
```

---

## 11) Update

```bash
sudo -u lighttrack -H git -C /opt/lighttracking pull
sudo -u lighttrack -H /opt/lighttracking/venv/bin/pip install -r /opt/lighttracking/pi/requirements.txt
sudo systemctl restart lighttracking
```
