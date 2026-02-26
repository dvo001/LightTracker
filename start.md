# Start der Umgebung (LightTracking)

Diese Datei dokumentiert den Start der LightTracking-Umgebung auf Linux/Raspberry Pi.

## 1. Voraussetzungen

- Repository liegt unter `/opt/lighttracking`
- Python 3 installiert
- MQTT Broker erreichbar (lokal oder im LAN)
- Optional: DMX Interface verbunden

## 2. Einmaliges Setup

```bash
cd /opt/lighttracking
python3 -m venv .venv
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install -r pi/requirements.txt
```

Wenn `No module named pip` erscheint:

```bash
.venv/bin/python -m ensurepip --upgrade
```

## 3. Start (Foreground, empfohlen)

`start.sh` setzt `PYTHONPATH` korrekt auf `pi/` und startet `uvicorn`.

```bash
cd /opt/lighttracking

# Beispiel fuer lokalen Broker
export MQTT_HOST=127.0.0.1
export MQTT_PORT=1883

# Optional
export LT_DB_PATH=/opt/lighttracking/pi/app/data/lighttracker.db
export DMX_UART_DEVICE=/dev/ttyUSB0

./start.sh
```

API ist danach standardmaessig auf `http://0.0.0.0:8000` erreichbar.

## 4. Schnell-Checks nach dem Start

```bash
curl -sS http://127.0.0.1:8000/api/v1/health | jq .
curl -sS http://127.0.0.1:8000/api/v1/state | jq .
curl -sS http://127.0.0.1:8000/api/v1/devices | jq .
curl -sS http://127.0.0.1:8000/api/v1/calibration/runs | jq '.runs[:3]'
```

## 5. Wichtige Settings

MQTT Host/Port koennen per API gesetzt werden:

```bash
curl -sS -X PUT http://127.0.0.1:8000/api/v1/settings \
  -H 'Content-Type: application/json' \
  -d '{"key":"mqtt.host","value":"127.0.0.1"}'

curl -sS -X PUT http://127.0.0.1:8000/api/v1/settings \
  -H 'Content-Type: application/json' \
  -d '{"key":"mqtt.port","value":"1883"}'
```

Aktuelle Werte pruefen:

```bash
curl -sS http://127.0.0.1:8000/api/v1/settings | jq '.settings[] | select(.key|test("^mqtt\\."))'
```

Provisioning-Bridge (ESP-NOW) nutzt zusaetzlich:

- `provision.bridge_port` (Pi GPIO UART meist `/dev/serial0`)
- `provision.bridge_baud` (meist `115200`)
- `provision.token` (Shared Secret)
- Optional GPIO-Steuerung fuer ESP Reset/Boot (nur wenn Pi diese Leitungen nutzt):
  - `provision.bridge_gpio_enabled` (`1`/`0`)
  - `provision.bridge_reset_pin` (Default auf Pi: `17`)
  - `provision.bridge_boot_pin` (Default auf Pi: `27`)
  - `provision.bridge_auto_reset` (Default auf Pi: `1`)

DMX-Ausgabe ueber USB-Bridge (PC -> ESP -> DMX auf ESP GPIO36/37):

- API `PUT /api/v1/dmx/config`
- `mode="bridge"`
- `bridge_port` (z.B. `/dev/ttyUSB0`)
- `bridge_baud` (Standard `115200`)
- Optional fuer hoehere Raten: Bridge-Firmware und Setting gemeinsam auf `921600`
- Bridge-Firmware DMX Pins:
  - `BRIDGE_DMX_TX_PIN=36`
  - `BRIDGE_DMX_RX_PIN=37`

Beispiel:

```bash
curl -sS -X PUT http://127.0.0.1:8000/api/v1/settings \
  -H 'Content-Type: application/json' \
  -d '{"key":"provision.bridge_port","value":"/dev/serial0"}'

curl -sS -X PUT http://127.0.0.1:8000/api/v1/settings \
  -H 'Content-Type: application/json' \
  -d '{"key":"provision.bridge_baud","value":"115200"}'

curl -sS -X PUT http://127.0.0.1:8000/api/v1/settings \
  -H 'Content-Type: application/json' \
  -d '{"key":"provision.bridge_gpio_enabled","value":"1"}'

curl -sS -X PUT http://127.0.0.1:8000/api/v1/dmx/config \
  -H 'Content-Type: application/json' \
  -d '{"mode":"bridge","bridge_port":"/dev/ttyUSB0","bridge_baud":115200}'
```

OLED-Statusanzeige an der Bridge (SSD1306, 128x64, gelbe obere Zeile):

- Standard-I2C in der Bridge-Firmware:
  - `BRIDGE_OLED_SDA_PIN=39`
  - `BRIDGE_OLED_SCL_PIN=38`
  - `BRIDGE_OLED_I2C_ADDR=0x3C`
- Verdrahtung:
  - `VCC -> 3V3`
  - `GND -> GND`
  - `SDA -> GPIO39`
  - `SCL -> GPIO38`
- Anzeige in der ersten (gelben) Zeile:
  - `DMX:--/OK/ERR`
  - `ESP:--/OK/ERR`

## 6. Systemd Betrieb (Dauerbetrieb)

```bash
cd /opt/lighttracking
sudo cp deploy/lighttracking.env /etc/lighttracking.env
sudo cp deploy/lighttracking.service /etc/systemd/system/lighttracking.service
sudo systemctl daemon-reload
sudo systemctl enable --now lighttracking
sudo systemctl status lighttracking --no-pager
```

Empfohlene Anpassung fuer die Unit:

- `ExecStart` auf das venv-Binary setzen:
  `/opt/lighttracking/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`
- `Environment=PYTHONPATH=/opt/lighttracking/pi` setzen

Danach:

```bash
sudo systemctl daemon-reload
sudo systemctl restart lighttracking
```

## 7. Stop/Restart/Logs

```bash
sudo systemctl stop lighttracking
sudo systemctl restart lighttracking
sudo journalctl -u lighttracking -f
```

## 8. LIVE Transition Hinweis

State API erwartet:

```json
{"state":"LIVE"}
```

Nicht:

```json
{"target_state":"LIVE"}
```
