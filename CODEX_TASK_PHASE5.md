# CODEX TASK – Phase 5 (Firmware Anchor/Tag + AT Adapter + MQTT cmd/ack + SIM Mode)

## Ziel (Phase 5 Scope)
Implementiere Phase 5 im Repo **LightTracking** (PlatformIO, Makerfabs MaUWB_ESP32S3):
1) **Gemeinsame Firmware-Bibliothek** (WiFi+MQTT, Identity, JSON Payloads, Cmd/Ack)
2) **Anchor Firmware**: Status + Range-Batch Publish
3) **Tag Firmware**: Status + (minimal) ranging participation
4) **AT Adapter Layer** für UWB (austauschbare Command-Map; robustes Parsing)
5) **SIM Mode** (compile flag) für Entwicklung ohne echte UWB/AT Ausgaben
6) **Interoperabilität** mit Pi (Topics + Payloads exakt gemäß Brief)

## Harte Vorgaben
- MAC ist Primary ID (aus esp_read_mac).
- MQTT Broker: host/port aus compile-time defaults + optional runtime cmd `apply_network` (optional v2).
- Command handling:
  - subscribe `dev/<mac_nocolon>/cmd` (QoS1)
  - publish `dev/<mac_nocolon>/cmd_ack` (QoS1)
- Status publish:
  - on boot + periodic heartbeat (default 5s)
- Range publish (Anchor):
  - batch_period_ms default 100ms (per cmd konfigurierbar)
- Robustheit:
  - reconnect loops mit backoff
  - bei parse errors: count + include in status fields

---

## Deliverables (Phase 5)

### A) PlatformIO Setup
**Dateien:**
- `firmware/platformio.ini`
- `firmware/common/*`
- `firmware/anchor/*`
- `firmware/tag/*`

**Anforderungen:**
- Separate environments: `anchor` und `tag` (oder separate projects, aber buildbar)
- Arduino framework (für schnelle v1) oder ESP-IDF nur wenn bereits gesetzt; v1: Arduino OK.
- Dependencies:
  - WiFi
  - MQTT client (z.B. `knolleary/PubSubClient` oder `256dpi/arduino-mqtt`)
  - JSON (ArduinoJson)
- Build flags:
  - `-DROLE_ANCHOR` / `-DROLE_TAG`
  - `-DSIM_RANGES` (optional)
  - `-DMQTT_HOST="192.168.1.10"` (default; anpassbar)
  - `-DMQTT_PORT=1883`

### B) Common Library (firmware/common)
Implementiere folgende Module (Header + ggf. CPP):

1) `device_identity.*`
- `String mac_colon()` returns "AA:BB:.."
- `String mac_nocolon()` returns "AABB.."
- role string "ANCHOR"/"TAG"
- fw version constant

2) `mqtt_client.*`
- connect WiFi (SSID/PW compile-time for v1; später per cmd)
- connect MQTT (host/port)
- subscribe cmd topic
- publish helper (topic, json)
- loop() in main

3) `json_payloads.*`
- build status payload
- build cmd_ack payload
- build range batch payload
- JSON schema exakt wie in Brief:

Status (minimal):
{
  "v":1,"type":"status","mac":"AA:BB:..","role":"ANCHOR","fw":"0.1.0","ts_ms":..., "status":"ONLINE",
  "ip":"192.168.1.21",
  "counters":{"mqtt_reconnects":..,"parse_errors":..}
}

Cmd/Ack:
cmd topic payload from Pi:
{ "v":1,"type":"cmd","cmd":"apply_settings","cmd_id":"...","settings":{"batch_period_ms":100} }

ack to Pi:
{ "v":1,"type":"cmd_ack","cmd_id":"...","result":"ok","details":{} }

Range batch (Anchor):
{
  "v":1,"type":"ranges","anchor_mac":"AA:BB:..","ts_ms":..., "seq":..., "src":"uwb_at",
  "ranges":[ {"tag_mac":"11:22:..","d_m":3.421,"q":0.86,"nlos":false,"err":0} ]
}

4) `cmd_handler.*`
- parse cmd JSON
- apply `apply_settings`:
  - batch_period_ms (anchor) / maybe tag ping period
- respond cmd_ack ok/error with details
- unknown cmd -> ack error

### C) AT Adapter Layer (firmware/common or role-specific)
**Ziel:** Kapsle UWB AT Details sauber.

Implementiere:
- `uwb_at_adapter.*`
  - `begin(Stream& serial)`
  - `poll()` reads lines, parses
  - `get_latest_ranges()` or callback-based emission
  - `set_role_anchor()` / `set_role_tag()` (stubs ok, TODO until real AT map known)

Parsing:
- tolerant line parser
- if AT syntax unknown, implement a pluggable regex/handler map:
  - vector of {pattern, handler}
- count parse_errors

### D) Anchor main.cpp
**Behavior:**
- init identity, WiFi, MQTT
- init AT adapter on UART (define pins/port appropriate for module; TODO if unknown)
- periodic status publish (5s)
- batch loop:
  - if SIM_RANGES: generate synthetic distances to one tag
  - else: read from AT adapter
  - publish range batch every batch_period_ms
- subscribe cmd topic and handle apply_settings

### E) Tag main.cpp
**Behavior (v1 minimal):**
- init identity, WiFi, MQTT
- status heartbeat
- AT adapter role TAG (stub ok)
- optional: SIM mode publishes a tag heartbeat; ranging participation depends on module AT firmware

### F) Interop Tests / Docs
- Update `firmware/README.md`:
  - how to set SSID/PW, MQTT host
  - how to build anchor/tag env
  - how to enable SIM_RANGES
- Optional: Provide a simple python script under `pi/tools/` to subscribe and print incoming status/ranges for debugging.

---

## Definition of Done (Phase 5)
- `pio run -e anchor` und `pio run -e tag` builden erfolgreich.
- Anchor publiziert status und ranges (SIM_RANGES mindestens).
- Cmd/Ack funktioniert: batch_period_ms kann per MQTT cmd geändert werden.
- Payloads entsprechen dem Schema, Pi kann sie ingestieren (smoke test via mosquitto_sub).
