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
#include <esp_wifi.h>
#include <Preferences.h>

PiMqttClient mqtt;
CmdHandler cmdh;
UwbAtAdapter at;
LtDisplay ldisplay;

unsigned long last_status = 0;
unsigned long last_star = 0;
bool star_on = false;
unsigned long seq = 0;
std::vector<std::pair<String, float>> range_buf;
int last_visible_tags = 0;
String anchor_mac;
int uwb_anchor_index = UWB_ANCHOR_INDEX;
constexpr int kUwbUartRx =
#ifdef UWB_UART_RX
  UWB_UART_RX;
#else
  -1;
#endif
constexpr int kUwbUartTx =
#ifdef UWB_UART_TX
  UWB_UART_TX;
#else
  -1;
#endif
constexpr int kUwbUartBaud =
#ifdef UWB_UART_BAUD
  UWB_UART_BAUD;
#else
  115200;
#endif
#ifndef UWB_TAG_COUNT
#define UWB_TAG_COUNT 64
#endif
#ifndef UWB_PAN_INDEX
#define UWB_PAN_INDEX 0
#endif
#ifndef UWB_AT_CONFIG
#define UWB_AT_CONFIG 1
#endif
#ifndef UWB_AT_RESTART
#define UWB_AT_RESTART 1
#endif

static int load_anchor_index_from_nvs() {
  Preferences prefs;
  prefs.begin("lt_cfg", true);
  int idx = prefs.getInt("anchor_index", UWB_ANCHOR_INDEX);
  prefs.end();
  return idx;
}

static void store_anchor_index_to_nvs(int idx) {
  Preferences prefs;
  prefs.begin("lt_cfg", false);
  prefs.putInt("anchor_index", idx);
  prefs.end();
}

static int parse_tag_id(const String& key) {
  if (!key.length()) return -1;
  if (key[0] == 'T' || key[0] == 't') {
    return key.substring(1).toInt();
  }
  return key.toInt();
}

static void store_tag_map_entry(int tid, const String& mac) {
  Preferences prefs;
  prefs.begin("lt_cfg", false);
  String key = String("tag_map_") + String(tid);
  if (mac.length()) {
    prefs.putString(key.c_str(), mac);
  } else {
    prefs.remove(key.c_str());
  }
  prefs.end();
}

static void load_tag_map_from_nvs() {
  Preferences prefs;
  prefs.begin("lt_cfg", true);
  for (int i = 0; i < 8; i++) {
    String key = String("tag_map_") + String(i);
    String mac = prefs.getString(key.c_str(), "");
    mac.trim();
    if (mac.length()) {
      mac.toUpperCase();
      at.set_tag_mac(i, mac);
      Serial.printf("uwb: tag_map[%d]=%s\n", i, mac.c_str());
    }
  }
  prefs.end();
}

static void apply_tag_map_settings(JsonObjectConst settings) {
  if (!settings.containsKey("tag_map")) return;
  JsonObjectConst map = settings["tag_map"].as<JsonObjectConst>();
  if (map.isNull()) return;
  for (JsonPairConst kv : map) {
    String key = String(kv.key().c_str());
    int tid = parse_tag_id(key);
    if (tid < 0 || tid > 7) continue;
    String mac = kv.value().as<String>();
    mac.trim();
    mac.toUpperCase();
    if (!mac.length()) {
      at.set_tag_mac(tid, "");
      store_tag_map_entry(tid, "");
      Serial.printf("uwb: tag_map[%d] cleared\n", tid);
      continue;
    }
    at.set_tag_mac(tid, mac);
    store_tag_map_entry(tid, mac);
    Serial.printf("uwb: tag_map[%d]=%s\n", tid, mac.c_str());
  }
}

static void uwb_send_cmd(const char* cmd, unsigned long wait_ms);

static void apply_anchor_index_settings(JsonObjectConst settings) {
  if (!settings.containsKey("anchor_index") && !settings.containsKey("uwb_anchor_index")) return;
  int idx = settings.containsKey("anchor_index") ? int(settings["anchor_index"]) : int(settings["uwb_anchor_index"]);
  if (idx < 0 || idx > 7) {
    Serial.printf("uwb: anchor_index %d invalid\n", idx);
    return;
  }
  if (idx == uwb_anchor_index) return;
  uwb_anchor_index = idx;
  at.set_anchor_index(idx);
  store_anchor_index_to_nvs(idx);
  Serial.printf("uwb: anchor_index=%d\n", idx);
  if (kUwbUartRx >= 0 && kUwbUartTx >= 0) {
    char cmd[64];
    snprintf(cmd, sizeof(cmd), "AT+SETCFG=%d,1,1,1", uwb_anchor_index);
    uwb_send_cmd(cmd, 200);
    snprintf(cmd, sizeof(cmd), "AT+SETCAP=%d,10,1", UWB_TAG_COUNT);
    uwb_send_cmd(cmd, 200);
    uwb_send_cmd("AT+SETRPT=1", 200);
    snprintf(cmd, sizeof(cmd), "AT+SETPAN=%d", UWB_PAN_INDEX);
    uwb_send_cmd(cmd, 200);
    uwb_send_cmd("AT+SAVE", 200);
#if UWB_AT_RESTART
    uwb_send_cmd("AT+RESTART", 200);
#endif
  }
}

static void uwb_send_cmd(const char* cmd, unsigned long wait_ms = 80) {
  Serial1.println(cmd);
  unsigned long start = millis();
  String line;
  while (millis() - start < wait_ms) {
    while (Serial1.available()) {
      char c = (char)Serial1.read();
      if (c == '\r') continue;
      if (c == '\n') {
#ifdef UWB_AT_DEBUG
        if (line.length()) Serial.printf("uwb: %s\n", line.c_str());
#endif
        line = "";
      } else {
        line += c;
      }
    }
    delay(1);
  }
}

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("anchor: boot");
  uint8_t mac[6]; esp_read_mac(mac, ESP_MAC_WIFI_STA);
  anchor_mac = String(mac[0], HEX) + ":" + String(mac[1], HEX) + ":" + String(mac[2], HEX) + ":" +
               String(mac[3], HEX) + ":" + String(mac[4], HEX) + ":" + String(mac[5], HEX);
  anchor_mac.toUpperCase();
  Serial.printf("anchor: mac=%s\n", anchor_mac.c_str());
  mqtt.load_config_from_nvs();
  load_tag_map_from_nvs();
  uwb_anchor_index = load_anchor_index_from_nvs();
  at.set_anchor_index(uwb_anchor_index);
  WiFi.mode(WIFI_STA);
  mqtt.begin();
  Serial.printf("anchor cfg: ssid='%s' pass_len=%d mqtt=%s:%d\n",
                mqtt.wifi_ssid.c_str(),
                mqtt.wifi_pass.length(),
                mqtt.mqtt_host.c_str(),
                mqtt.mqtt_port);
  uint8_t ch=0; wifi_second_chan_t sc=WIFI_SECOND_CHAN_NONE;
  esp_wifi_get_channel(&ch, &sc);
  Serial.printf("anchor: channel=%u second=%u\n", ch, (unsigned)sc);
  mqtt.on_cmd = [](const String& topic, const String& payload){
    cmdh.handle(payload.c_str(), mqtt);
  };
  cmdh.on_settings = [](JsonObjectConst settings) {
    apply_anchor_index_settings(settings);
    apply_tag_map_settings(settings);
  };
#ifndef SIM_RANGES
  at.on_range = [](const String& tag_mac, float d_m) {
    if (range_buf.size() < 32) range_buf.push_back({tag_mac, d_m});
  };
#endif
  if (kUwbUartRx >= 0 && kUwbUartTx >= 0){
    Serial1.begin(kUwbUartBaud, SERIAL_8N1, kUwbUartRx, kUwbUartTx);
    at.begin(Serial1);
    Serial.printf("uwb: uart1 rx=%d tx=%d baud=%d\n", kUwbUartRx, kUwbUartTx, kUwbUartBaud);
#if UWB_AT_CONFIG
    Serial.printf("uwb: config anchor_index=%d tag_count=%d\n", uwb_anchor_index, UWB_TAG_COUNT);
    char cmd[64];
    uwb_send_cmd("AT");
    snprintf(cmd, sizeof(cmd), "AT+SETCFG=%d,1,1,1", uwb_anchor_index);
    uwb_send_cmd(cmd, 200);
    snprintf(cmd, sizeof(cmd), "AT+SETCAP=%d,10,1", UWB_TAG_COUNT);
    uwb_send_cmd(cmd, 200);
    uwb_send_cmd("AT+SETRPT=1", 200);
    snprintf(cmd, sizeof(cmd), "AT+SETPAN=%d", UWB_PAN_INDEX);
    uwb_send_cmd(cmd, 200);
    uwb_send_cmd("AT+SAVE", 200);
#if UWB_AT_RESTART
    uwb_send_cmd("AT+RESTART", 200);
#endif
#endif
  } else {
    Serial.println("uwb: uart not configured (set UWB_UART_RX/TX)");
  }
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
  if (now - last_status >= (unsigned long)cmdh.heartbeat_ms) {
    String ip = WiFi.localIP().toString();
    String st = JsonPayloads::status_payload("ONLINE", ip.c_str(), millis(), mqtt.reconnects, at.parse_errors);
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
    bool espnow_ok = prov_is_active();
    if (espnow_ok && millis() - last_star > 500){
      last_star = millis();
      star_on = !star_on;
    }
    if (!espnow_ok) star_on = false;
    ldisplay.draw(alias, "Anchor", last_visible_tags, WiFi.status() == WL_CONNECTED, rssi, true, espnow_ok, star_on);
    last_disp = millis();
  }
}
