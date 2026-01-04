#pragma once
#include <ArduinoJson.h>
#include "json_payloads.h"
#include "device_identity.h"
#include "mqtt_client.h"

class CmdHandler {
public:
  int batch_period_ms = 100;
  int heartbeat_ms = 5000;

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
        JsonObject settings = doc["settings"];
        bool net_changed = false;
        String ssid = settings["ssid"] | "";
        String pass = settings["pass"] | "";
        String host = settings["mqtt_host"] | "";
        int port = settings.containsKey("mqtt_port") ? int(settings["mqtt_port"]) : -1;
        if (settings.containsKey("alias")) {
          String alias = settings["alias"].as<String>();
          mqtt.apply_alias(alias);
        }
        if (doc.containsKey("settings") && doc["settings"].containsKey("batch_period_ms")) {
          batch_period_ms = doc["settings"]["batch_period_ms"];
        }
        if (doc.containsKey("settings") && doc["settings"].containsKey("heartbeat_ms")) {
          heartbeat_ms = doc["settings"]["heartbeat_ms"];
        }
        if (ssid.length() || host.length() || port > 0) {
          mqtt.apply_network_settings(ssid, pass, host, port);
          net_changed = true;
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
