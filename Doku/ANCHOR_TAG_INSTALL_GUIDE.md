# LightTracking – ANCHOR & TAG INSTALLATION GUIDE
(Makerfabs MaUWB_ESP32S3 – SKU MAUWBS3CA1)

Diese Anleitung beschreibt die **Inbetriebnahme der Anchor- und Tag-Module**.

---

## 1) Voraussetzungen
- Makerfabs MaUWB_ESP32S3 (Anchor/Tag)
- Flash-Kabel (USB)
- PlatformIO (VS Code)
- Zugang zum LightTracking MQTT Broker (LAN)

---

## 2) Firmware flashen

### Projekt öffnen
```text
LightTracking/firmware/
```

### PlatformIO
- VS Code → PlatformIO
- Environments:
  - `anchor`
  - `tag`

### Build & Upload
```bash
pio run -e anchor -t upload
pio run -e tag -t upload
```

---

## 3) WLAN & MQTT Konfiguration

### v1 (Compile-Time Defaults)
In `platformio.ini` oder Build Flags:
```ini
-DWIFI_SSID="YourSSID"
-DWIFI_PASSWORD="YourPassword"
-DMQTT_HOST="192.168.1.10"
-DMQTT_PORT=1883
```

Neu builden & flashen.

---

## 4) Einschalten & Erstkontakt

### Erwartetes Verhalten
- LED an / Boot-Sequenz
- Verbindung mit WLAN
- MQTT connect
- Status Publish:
```json
{
  "type": "status",
  "role": "ANCHOR",
  "mac": "AA:BB:CC:DD:EE:FF",
  "status": "ONLINE"
}
```

Auf dem Pi:
```bash
mosquitto_sub -t 'dev/+/status' -v
```

---

## 5) Anchor vs Tag

### Anchor
- Rolle: ANCHOR
- Sendet Range-Batches (`dev/<mac>/ranges`)
- Batch-Rate per MQTT cmd konfigurierbar

### Tag
- Rolle: TAG
- Nimmt am Ranging teil
- Sendet Status (v1 minimal)

---

## 6) SIM_RANGES Mode (Entwicklung)

### Aktivieren
```ini
build_flags =
  -DSIM_RANGES
```

### Verhalten
- Anchor erzeugt synthetische Distanzen
- Ideal für Tests ohne reale UWB-Hardware

---

## 7) MQTT Cmd / Ack Test

```bash
mosquitto_pub -t dev/<mac_nocolon>/cmd -m '{
  "v":1,
  "type":"cmd",
  "cmd":"apply_settings",
  "cmd_id":"test-001",
  "settings":{"batch_period_ms":200}
}'
```

Erwartetes Ack:
```bash
mosquitto_sub -t dev/<mac_nocolon>/cmd_ack -v
```

---

## 8) Typische Fehler

### Kein Status
- WLAN Credentials falsch?
- MQTT Host erreichbar?
- MAC-Adresse korrekt gelesen?

### Keine Ranges
- SIM_RANGES aktiv?
- AT Adapter liefert Daten?
- batch_period_ms zu hoch/niedrig?

---

## 9) Nächste Schritte
- Anchor-Positionen messen & eintragen
- Kalibrieren
- LIVE_CHECKLIST.md folgen

