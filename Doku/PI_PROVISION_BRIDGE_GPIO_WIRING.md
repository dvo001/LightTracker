# Raspberry Pi Provisioning Bridge per GPIO/UART

Diese Anleitung beschreibt, wie der Provisioning-Bridge-Link direkt ueber die
UART-GPIO Pins des Raspberry Pi aufgebaut wird.

## 1) Verdrahtung (3.3V TTL, kein 5V)

- Pi Pin 8 (`GPIO14 / TXD0`) -> Bridge `RX`
- Pi Pin 10 (`GPIO15 / RXD0`) -> Bridge `TX`
- Pi Pin 6 (`GND`) -> Bridge `GND`

Optional:
- Pi Pin 1 (`3V3`) -> Bridge `3V3` (nur wenn Stromaufnahme sicher passt)
- Pi Pin 11 (`GPIO17`) -> Bridge `EN/RST`
- Pi Pin 13 (`GPIO27`) -> Bridge `BOOT/GPIO0`

Wichtig:
- TX/RX immer gekreuzt verbinden (Pi TX -> Device RX, Pi RX -> Device TX)
- Gemeinsame Masse (`GND`) ist Pflicht
- Nur 3.3V Logikpegel verwenden

## 2) UART am Pi aktivieren

```bash
sudo raspi-config
```

Dann:
- `Interface Options -> Serial Port`
- Login Shell ueber Serial: `No`
- Hardware Serial aktivieren: `Yes`

Danach neu starten:

```bash
sudo reboot
```

Pruefen:

```bash
ls -l /dev/serial0
```

## 3) LightTracking auf `/dev/serial0` stellen

Provisioning nutzt die Settings:
- `provision.bridge_port`
- `provision.bridge_baud`

Per API setzen:

```bash
curl -X PUT http://localhost:8000/api/v1/settings \
  -H 'Content-Type: application/json' \
  -d '{"key":"provision.bridge_port","value":"/dev/serial0"}'

curl -X PUT http://localhost:8000/api/v1/settings \
  -H 'Content-Type: application/json' \
  -d '{"key":"provision.bridge_baud","value":"115200"}'
```

## 4) Kurzer Bridge-Test

Datei: `provision_bridge_pi_gpio.py`

```python
from provision_bridge_pi_gpio import ProvisionBridgeClient

with ProvisionBridgeClient("/dev/serial0", baud=115200) as client:
    print(client.hello())
```

Mit optionalen Reset/Boot Pins:

```python
from provision_bridge_pi_gpio import ProvisionBridgeClient

client = ProvisionBridgeClient(
    "/dev/serial0",
    baud=115200,
    reset_pin=17,
    boot_pin=27,
    auto_reset=True,
)
print(client.hello())
client.close()
```

## 5) Troubleshooting

- `bridge timeout`: TX/RX vertauscht, kein GND, falscher Baud
- `open failed`: User hat keine Rechte auf UART-Device
- Kein `/dev/serial0`: Serial in `raspi-config` nicht korrekt gesetzt

