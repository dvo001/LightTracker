#include <Arduino.h>
#include <vector>
#include <utility>
#include "common/device_identity.h"
#include "common/mqtt_client.h"
#include "common/json_payloads.h"
#include "common/cmd_handler.h"
#include "common/uwb_at_adapter.h"
#include "common/display.h"
#include "common/provisioning_espnow.h"

PiMqttClient mqtt;
CmdHandler cmdh;
UwbAtAdapter at;
LtDisplay ldisplay;

unsigned long last_status = 0;
unsigned long seq = 0;
std::vector<std::pair<String, float>> range_buf;
int last_visible_tags = 0;

void setup() {
  Serial.begin(115200);
  delay(100);
  mqtt.load_config_from_nvs();
  mqtt.begin();
  mqtt.on_cmd = [](const String& topic, const String& payload){
    cmdh.handle(payload.c_str(), mqtt);
  };
#ifndef SIM_RANGES
  at.on_range = [](const String& tag_mac, float d_m) {
    if (range_buf.size() < 32) range_buf.push_back({tag_mac, d_m});
  };
#endif
  ldisplay.begin();
  prov_init();
}

void loop() {
  prov_loop();
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
    // real mode: poll AT adapter and publish collected batch
    at.poll();
    if (!range_buf.empty()) {
      std::vector<String> uniq;
      StaticJsonDocument<1024> doc;
      doc["v"] = 1;
      doc["type"] = "ranges";
      doc["anchor_mac"] = DeviceIdentity::mac_colon();
      doc["ts_ms"] = millis();
      doc["seq"] = seq++;
      doc["src"] = "uwb_at";
      JsonArray narr = doc.createNestedArray("ranges");
      for (auto &it : range_buf) {
        JsonObject o = narr.createNestedObject();
        o["tag_mac"] = it.first;
        o["d_m"] = it.second;
        if (std::find(uniq.begin(), uniq.end(), it.first) == uniq.end()) {
          uniq.push_back(it.first);
        }
      }
      last_visible_tags = uniq.size();
      String payload;
      serializeJson(doc, payload);
      String topic = String("dev/") + DeviceIdentity::mac_nocolon() + "/ranges";
      mqtt.publish(topic, payload);
      range_buf.clear();
    }
#endif
    last_ranges = now;
  }

  delay(10);

  // display update (every ~1s)
  static unsigned long last_disp = 0;
  if (millis() - last_disp > 1000){
    int rssi = (WiFi.status() == WL_CONNECTED) ? WiFi.RSSI() : -127;
    String alias = mqtt.device_alias.length() ? mqtt.device_alias : String("Anchor");
    ldisplay.draw(alias, "Anchor", last_visible_tags, WiFi.status() == WL_CONNECTED, rssi);
    last_disp = millis();
  }
}
