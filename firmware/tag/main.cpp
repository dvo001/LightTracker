#include <Arduino.h>
#include "common/device_identity.h"
#include "common/mqtt_client.h"
#include "common/json_payloads.h"
#include "common/cmd_handler.h"
#include "common/display.h"
#include "common/provisioning_espnow.h"
#include <esp_wifi.h>

PiMqttClient mqtt;
CmdHandler cmdh;
LtDisplay ldisplay;

unsigned long last_status = 0;
unsigned long last_star = 0;
bool star_on = false;
String tag_mac;
wl_status_t last_wifi_status = WL_IDLE_STATUS;
unsigned long last_wifi_log = 0;

static const char* wifi_status_str(wl_status_t st){
  switch (st){
    case WL_IDLE_STATUS: return "IDLE";
    case WL_NO_SSID_AVAIL: return "NO_SSID";
    case WL_SCAN_COMPLETED: return "SCAN_DONE";
    case WL_CONNECTED: return "CONNECTED";
    case WL_CONNECT_FAILED: return "CONNECT_FAILED";
    case WL_CONNECTION_LOST: return "CONNECTION_LOST";
    case WL_DISCONNECTED: return "DISCONNECTED";
    default: return "UNKNOWN";
  }
}

static void log_wifi_scan_results(const String& target_ssid, int16_t n){
  if (n < 0){
    Serial.printf("wifi: scan failed (%d)\n", n);
    return;
  }
  int best_rssi = -127;
  int best_ch = 0;
  bool found = false;
  for (int i = 0; i < n; i++){
    if (WiFi.SSID(i) == target_ssid){
      found = true;
      int rssi = WiFi.RSSI(i);
      if (rssi > best_rssi){
        best_rssi = rssi;
        best_ch = WiFi.channel(i);
      }
    }
  }
  if (found){
    Serial.printf("wifi: scan ssid='%s' ch=%d rssi=%d\n",
                  target_ssid.c_str(), best_ch, best_rssi);
  } else {
    Serial.printf("wifi: scan ssid='%s' not found (n=%d)\n",
                  target_ssid.c_str(), n);
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("tag: boot");
  uint8_t mac[6]; esp_read_mac(mac, ESP_MAC_WIFI_STA);
  tag_mac = String(mac[0], HEX) + ":" + String(mac[1], HEX) + ":" + String(mac[2], HEX) + ":" +
            String(mac[3], HEX) + ":" + String(mac[4], HEX) + ":" + String(mac[5], HEX);
  tag_mac.toUpperCase();
  Serial.printf("tag: mac=%s\n", tag_mac.c_str());
  mqtt.load_config_from_nvs();
  WiFi.mode(WIFI_STA);
  mqtt.begin();
  Serial.printf("tag cfg: ssid='%s' pass_len=%d mqtt=%s:%d\n",
                mqtt.wifi_ssid.c_str(),
                mqtt.wifi_pass.length(),
                mqtt.mqtt_host.c_str(),
                mqtt.mqtt_port);
  uint8_t ch=0; wifi_second_chan_t sc=WIFI_SECOND_CHAN_NONE;
  esp_wifi_get_channel(&ch, &sc);
  Serial.printf("tag: channel=%u second=%u\n", ch, (unsigned)sc);
  mqtt.on_cmd = [](const String& topic, const String& payload){
    cmdh.handle(payload.c_str(), mqtt);
  };
  ldisplay.begin();
  if (!mqtt.has_wifi_cfg){
    prov_init();
  } else {
    Serial.println("prov: disabled (wifi config present)");
  }
}

void loop() {
  prov_loop();
  mqtt.loop();
  unsigned long now = millis();
  if (now - last_wifi_log > 5000 || WiFi.status() != last_wifi_status){
    last_wifi_status = WiFi.status();
    last_wifi_log = now;
    Serial.printf("wifi: status=%s rssi=%d ip=%s gw=%s dns=%s\n",
                  wifi_status_str(last_wifi_status),
                  (int)WiFi.RSSI(),
                  WiFi.localIP().toString().c_str(),
                  WiFi.gatewayIP().toString().c_str(),
                  WiFi.dnsIP().toString().c_str());
  }
  static bool scan_running = false;
  static unsigned long last_scan_ms = 0;
  const unsigned long scan_interval_ms = 15000;
  if (mqtt.wifi_ssid.length() && WiFi.status() != WL_CONNECTED){
    if (!scan_running && (now - last_scan_ms > scan_interval_ms)){
      int16_t started = WiFi.scanNetworks(true, false);
      if (started == WIFI_SCAN_RUNNING){
        scan_running = true;
        Serial.println("wifi: scan started");
      } else {
        log_wifi_scan_results(mqtt.wifi_ssid, started);
        WiFi.scanDelete();
        last_scan_ms = now;
      }
    }
    int16_t n = WiFi.scanComplete();
    if (scan_running && n >= 0){
      log_wifi_scan_results(mqtt.wifi_ssid, n);
      WiFi.scanDelete();
      scan_running = false;
      last_scan_ms = now;
    } else if (scan_running && n == WIFI_SCAN_FAILED){
      Serial.println("wifi: scan failed");
      WiFi.scanDelete();
      scan_running = false;
      last_scan_ms = now;
    }
  }
  static unsigned long last_mac_log = 0;
  if (now - last_mac_log > 5000){
    Serial.printf("tag: mac=%s\n", tag_mac.c_str());
    uint8_t ch=0; wifi_second_chan_t sc=WIFI_SECOND_CHAN_NONE;
    esp_wifi_get_channel(&ch, &sc);
    Serial.printf("tag: channel=%u second=%u\n", ch, (unsigned)sc);
    last_mac_log = now;
  }
  // keep ESP-NOW on channel 6 if not connected to WiFi
  static unsigned long last_ch_check = 0;
  if (prov_is_active() && WiFi.status() != WL_CONNECTED && (now - last_ch_check > 1000)){
    last_ch_check = now;
    uint8_t ch=0; wifi_second_chan_t sc=WIFI_SECOND_CHAN_NONE;
    esp_wifi_get_channel(&ch, &sc);
    if (ch != 6){
      esp_wifi_set_channel(6, WIFI_SECOND_CHAN_NONE);
      esp_wifi_get_channel(&ch, &sc);
      Serial.printf("tag: forced channel to %u (sec=%u)\n", ch, (unsigned)sc);
    }
  }
  if (now - last_status >= 5000) {
    String st = JsonPayloads::status_payload("ONLINE", "0.0.0.0", millis(), mqtt.reconnects, 0);
    String topic = String("dev/") + DeviceIdentity::mac_nocolon() + "/status";
    mqtt.publish(topic, st);
    last_status = now;
  }
  delay(10);

  // display update (every ~1s)
  static unsigned long last_disp = 0;
  if (millis() - last_disp > 1000){
    int rssi = (WiFi.status() == WL_CONNECTED) ? WiFi.RSSI() : -127;
    String alias = mqtt.device_alias.length() ? mqtt.device_alias : String("Tag");
    bool espnow_ok = prov_is_active();
    if (espnow_ok && millis() - last_star > 500){
      last_star = millis();
      star_on = !star_on;
    }
    if (!espnow_ok) star_on = false;
    // Tag: keine lokale Info über sichtbare Anchors, daher ohne Counter anzeigen
    ldisplay.draw(alias, "Tag", 0, WiFi.status() == WL_CONNECTED, rssi, false, espnow_ok, star_on);
    last_disp = millis();
  }
}
