#include <Arduino.h>
#include "common/device_identity.h"
#include "common/mqtt_client.h"
#include "common/json_payloads.h"
#include "common/cmd_handler.h"
#include "common/uwb_at_adapter.h"

PiMqttClient mqtt;
CmdHandler cmdh;
UwbAtAdapter at;

unsigned long last_status = 0;
unsigned long seq = 0;

void setup() {
  Serial.begin(115200);
  delay(100);
  // WiFi credentials must be provided at runtime or compiled-in TODO
  mqtt.begin("", "");
}

void loop() {
  mqtt.loop();
  unsigned long now = millis();
  if (now - last_status >= (unsigned long)cmdh.heartbeat_ms) {
    String st = JsonPayloads::status_payload("ONLINE", "0.0.0.0", millis(), mqtt.reconnects, at.parse_errors);
    String topic = String("dev/") + DeviceIdentity::mac_nocolon() + "/status";
    mqtt.publish(topic, st);
    last_status = now;
  }

  // ranges publish
  static unsigned long last_ranges = 0;
  if ((unsigned long)(now - last_ranges) >= (unsigned long)cmdh.batch_period_ms) {
#ifdef SIM_RANGES
    // generate simulated single tag range
    StaticJsonDocument<256> rarr;
    JsonArray arr = rarr.to<JsonArray>();
    JsonObject it = arr.createNestedObject();
    it["tag_mac"] = "AA:BB:CC:DD:EE:01";
    it["d_m"] = 3.14;
    String payload;
    // build using JsonPayloads helper by moving array
    // workaround: serialize arr into temp doc
    StaticJsonDocument<512> doc;
    doc["v"] = 1;
    doc["type"] = "ranges";
    doc["anchor_mac"] = DeviceIdentity::mac_colon();
    doc["ts_ms"] = millis();
    doc["seq"] = seq++;
    doc["src"] = "sim";
    JsonArray narr = doc.createNestedArray("ranges");
    JsonObject o = narr.createNestedObject();
    o["tag_mac"] = "AA:BB:CC:DD:EE:01";
    o["d_m"] = 3.14;
    serializeJson(doc, payload);
    String topic = String("dev/") + DeviceIdentity::mac_nocolon() + "/ranges";
    mqtt.publish(topic, payload);
#else
    // real mode: poll AT adapter and collect ranges
    at.poll();
    // TODO: collect from AT adapter callback and publish batch
#endif
    last_ranges = now;
  }

  delay(10);
}
