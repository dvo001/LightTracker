#pragma once
#include <ArduinoJson.h>
#include "json_payloads.h"
#include "device_identity.h"

class CmdHandler {
public:
  int batch_period_ms = 100;

  bool handle(const char* payload, PiMqttClient& mqtt) {
    StaticJsonDocument<512> doc;
    DeserializationError err = deserializeJson(doc, payload);
    if (err) {
      return false;
    }
    const char* type = doc["type"];
    if (strcmp(type, "cmd") == 0) {
      const char* cmd = doc["cmd"];
      const char* cmd_id = doc["cmd_id"];
      if (strcmp(cmd, "apply_settings") == 0) {
        if (doc.containsKey("settings") && doc["settings"].containsKey("batch_period_ms")) {
          batch_period_ms = doc["settings"]["batch_period_ms"];
        }
        String ack = JsonPayloads::cmd_ack_payload(cmd_id, "ok");
        String topic = String("dev/") + DeviceIdentity::mac_nocolon() + "/cmd_ack";
        mqtt.publish(topic, ack);
        return true;
      }
      // unknown cmd
      String ack = JsonPayloads::cmd_ack_payload(cmd_id, "error", "unknown_cmd");
      String topic = String("dev/") + DeviceIdentity::mac_nocolon() + "/cmd_ack";
      mqtt.publish(topic, ack);
      return false;
    }
    return false;
  }
};
