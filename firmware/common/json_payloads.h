#pragma once
#include <ArduinoJson.h>
#include <Arduino.h>
#include "device_identity.h"

namespace JsonPayloads {

inline String status_payload(const char* status, const char* ip, unsigned long ts_ms, int mqtt_reconnects, int parse_errors) {
  StaticJsonDocument<512> doc;
  doc["v"] = 1;
  doc["type"] = "status";
  doc["mac"] = DeviceIdentity::mac_colon();
  doc["role"] = DeviceIdentity::role();
  doc["fw"] = DeviceIdentity::fw_version();
  doc["ts_ms"] = ts_ms;
  doc["status"] = status;
  doc["ip"] = ip;
  JsonObject c = doc.createNestedObject("counters");
  c["mqtt_reconnects"] = mqtt_reconnects;
  c["parse_errors"] = parse_errors;
  String out;
  serializeJson(doc, out);
  return out;
}

inline String cmd_ack_payload(const char* cmd_id, const char* result, const char* details="") {
  StaticJsonDocument<256> doc;
  doc["v"] = 1;
  doc["type"] = "cmd_ack";
  doc["cmd_id"] = cmd_id;
  doc["result"] = result;
  if (details && strlen(details)) doc["details"] = details;
  String out; serializeJson(doc, out); return out;
}

inline String ranges_payload(unsigned long ts_ms, unsigned long seq, const JsonArray& ranges_array) {
  StaticJsonDocument<1024> doc;
  doc["v"] = 1;
  doc["type"] = "ranges";
  doc["anchor_mac"] = DeviceIdentity::mac_colon();
  doc["ts_ms"] = ts_ms;
  doc["seq"] = seq;
  doc["src"] = "uwb_at";
  JsonArray arr = doc.createNestedArray("ranges");
  for (JsonObject o : ranges_array) {
    JsonObject it = arr.createNestedObject();
    it["tag_mac"] = o["tag_mac"];
    it["d_m"] = o["d_m"];
    if (o.containsKey("q")) it["q"] = o["q"];
    if (o.containsKey("nlos")) it["nlos"] = o["nlos"];
    if (o.containsKey("err")) it["err"] = o["err"];
  }
  String out; serializeJson(doc, out); return out;
}

}
// JSON payload helpers
