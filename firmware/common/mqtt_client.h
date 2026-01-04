#pragma once
#include <WiFi.h>
#include <PubSubClient.h>
#include <Preferences.h>
#include <functional>
#include "device_identity.h"
#include "json_payloads.h"

class PiMqttClient;
static PiMqttClient* _lt_active_mqtt = nullptr;
static void _lt_mqtt_callback(char* topic, uint8_t* payload, unsigned int len);

class PiMqttClient {
public:
  WiFiClient espClient;
  PubSubClient client{espClient};
  Preferences prefs;
  String wifi_ssid = "";
  String wifi_pass = "";
  String mqtt_host = MQTT_HOST;
  int mqtt_port = MQTT_PORT;
  String device_alias = "";
  unsigned long lastReconnectAttempt = 0;
  int reconnects = 0;
  int parse_errors = 0;
  std::function<void(const String&, const String&)> on_cmd = nullptr;

  PiMqttClient() {
    client.setServer(mqtt_host.c_str(), mqtt_port);
  }

  void load_config_from_nvs() {
    prefs.begin("lt_cfg", true);
    wifi_ssid = prefs.getString("ssid", wifi_ssid);
    wifi_pass = prefs.getString("pass", wifi_pass);
    mqtt_host = prefs.getString("mqtt_host", mqtt_host);
    mqtt_port = prefs.getInt("mqtt_port", mqtt_port);
    device_alias = prefs.getString("alias", device_alias);
    prefs.end();
    client.setServer(mqtt_host.c_str(), mqtt_port);
  }

  void save_config_to_nvs() {
    prefs.begin("lt_cfg", false);
    prefs.putString("ssid", wifi_ssid);
    prefs.putString("pass", wifi_pass);
    prefs.putString("mqtt_host", mqtt_host);
    prefs.putInt("mqtt_port", mqtt_port);
    prefs.putString("alias", device_alias);
    prefs.end();
  }

  void begin() {
    _lt_active_mqtt = this;
    client.setCallback(_lt_mqtt_callback);
    if (wifi_ssid.length()) {
      WiFi.begin(wifi_ssid.c_str(), wifi_pass.c_str());
    }
  }

  bool reconnect() {
    if (client.connected()) return true;
    if (WiFi.status() != WL_CONNECTED && wifi_ssid.length()) {
      WiFi.begin(wifi_ssid.c_str(), wifi_pass.c_str());
      delay(100);
    }
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

  void apply_network_settings(const String& ssid, const String& pass, const String& host, int port) {
    if (ssid.length()) wifi_ssid = ssid;
    if (pass.length() || ssid.length()) wifi_pass = pass; // allow empty pass if ssid provided
    if (host.length()) mqtt_host = host;
    if (port > 0) mqtt_port = port;
    client.setServer(mqtt_host.c_str(), mqtt_port);
    save_config_to_nvs();
    if (wifi_ssid.length()) {
      WiFi.disconnect();
      delay(100);
      WiFi.begin(wifi_ssid.c_str(), wifi_pass.c_str());
    }
    lastReconnectAttempt = 0; // force immediate reconnect
    reconnect();
  }

  void apply_alias(const String& alias) {
    device_alias = alias;
    save_config_to_nvs();
  }

  void dispatch_message(char* topic, uint8_t* payload, unsigned int len) {
    if (!on_cmd) return;
    String t(topic);
    String p;
    p.reserve(len);
    for (unsigned int i = 0; i < len; i++) p += (char)payload[i];
    on_cmd(t, p);
  }
};

static void _lt_mqtt_callback(char* topic, uint8_t* payload, unsigned int len){
  if (_lt_active_mqtt){
    _lt_active_mqtt->dispatch_message(topic, payload, len);
  }
}
// MQTT client abstraction
