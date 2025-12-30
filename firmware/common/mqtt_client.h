#pragma once
#include <WiFi.h>
#include <PubSubClient.h>
#include "device_identity.h"
#include "json_payloads.h"

class PiMqttClient {
public:
  WiFiClient espClient;
  PubSubClient client{espClient};
  const char* host = MQTT_HOST;
  int port = MQTT_PORT;
  unsigned long lastReconnectAttempt = 0;
  int reconnects = 0;
  int parse_errors = 0;

  PiMqttClient() {
    client.setServer(host, port);
  }

  void begin(const char* ssid, const char* pass) {
    WiFi.begin(ssid, pass);
  }

  bool reconnect() {
    if (client.connected()) return true;
    unsigned long now = millis();
    if (now - lastReconnectAttempt < 5000) return false;
    lastReconnectAttempt = now;
    if (client.connect(DeviceIdentity::mac_nocolon().c_str())) {
      reconnects++;
      // subscribe cmd topic
      String topic = String("dev/") + DeviceIdentity::mac_nocolon() + "/cmd";
      client.subscribe(topic.c_str(), 1);
      return true;
    }
    return false;
  }

  void loop() {
    if (!client.connected()) reconnect();
    client.loop();
  }

  bool publish(const String& topic, const String& payload, int qos=0) {
    return client.publish(topic.c_str(), payload.c_str());
  }
};
// MQTT client abstraction
