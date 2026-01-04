#include "provisioning_espnow.h"
#include <esp_wifi.h>
#include <esp_now.h>
#include <Preferences.h>
#include "pb_proto.h"
#include <ArduinoJson.h>
#include "mqtt_client.h"
#include "cbor_codec.h"

static uint8_t g_last_src[6] = {0};
static uint16_t g_last_seq = 0;
static uint8_t g_last_msg = 0;
static std::vector<uint8_t> g_last_response;
static Preferences prefs;
static String g_token = "changeme"; // configure as needed
static bool g_cfg_applied = false;
static bool g_frag_active = false;
static uint8_t g_frag_src[6] = {0};
static uint16_t g_frag_seq = 0;
static uint8_t g_frag_msg = 0;
static uint8_t g_frag_cnt = 0;
static uint32_t g_frag_last_ms = 0;
static std::vector<std::vector<uint8_t>> g_frags;

static String get_pref(const char* key, const String& def=""){
  return prefs.getString(key, def);
}
static void set_pref(const char* key, const String& val){ prefs.putString(key, val); }
static void set_pref_int(const char* key, int v){ prefs.putInt(key, v); }
static int get_pref_int(const char* key, int defv){ return prefs.getInt(key, defv); }

static PiMqttClient* g_mqtt = nullptr;

void prov_init(){
  WiFi.mode(WIFI_STA);
  esp_wifi_set_channel(6, WIFI_SECOND_CHAN_NONE);
  esp_now_init();
  // TODO: register recv callback, set up dedup cache, NVS schema, handlers
  prefs.begin("prov", false);
  // allow linking to global MQTT client if exists
  g_mqtt = _lt_active_mqtt;
}

static bool is_duplicate(uint16_t seq, uint8_t msg, const uint8_t* src){
  return (seq == g_last_seq) && (msg == g_last_msg) && memcmp(src, g_last_src, 6) == 0;
}

static void remember(uint16_t seq, uint8_t msg, const uint8_t* src, const std::vector<uint8_t>& resp){
  g_last_seq = seq; g_last_msg = msg; memcpy(g_last_src, src, 6); g_last_response = resp;
}

static void send_raw(const uint8_t* dest, const std::vector<uint8_t>& data){
  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, dest, 6);
  peer.channel = 6;
  peer.encrypt = false;
  esp_now_del_peer(peer.peer_addr);
  esp_now_add_peer(&peer);
  esp_now_send(peer.peer_addr, data.data(), data.size());
}

static void send_nack(const uint8_t* src, uint16_t seq, const char* code, const char* msg){
  PbHeader hdr;
  hdr.msg_type = PB_NACK;
  hdr.seq = seq;
  DynamicJsonDocument doc(128);
  doc["code"] = code;
  doc["msg"] = msg;
  auto payload = cbor_encode_json(doc.as<JsonVariantConst>());
  hdr.payload_len = payload.size();
  auto frame = pb_build_frame(hdr, payload.data(), payload.size());
  send_raw(src, frame);
  remember(seq, PB_NACK, src, frame);
}

static void on_recv(const uint8_t *mac, const uint8_t *data, int len){
  PbHeader hdr;
  if (!pb_parse_header(data, len, hdr)) return;
  const uint8_t* payload = data + PB_HDR_SIZE;
  size_t paylen = len - PB_HDR_SIZE;
  // reassembly
  if (hdr.flags & PB_FLAG_IS_FRAG){
    if (!g_frag_active || memcmp(g_frag_src, mac, 6)!=0 || g_frag_seq!=hdr.seq || g_frag_msg!=hdr.msg_type){
      g_frag_active = true;
      memcpy(g_frag_src, mac, 6);
      g_frag_seq = hdr.seq;
      g_frag_msg = hdr.msg_type;
      g_frag_cnt = hdr.frag_cnt;
      g_frags.assign(g_frag_cnt, {});
    }
    if (hdr.frag_idx < g_frags.size()){
      g_frags[hdr.frag_idx].assign(payload, payload+paylen);
      g_frag_last_ms = millis();
    }
    bool complete = true;
    for (uint8_t i=0;i<g_frag_cnt;i++){
      if (g_frags[i].empty()) { complete=false; break; }
    }
    if (!complete) return;
    // concat
    std::vector<uint8_t> full;
    for (auto& f : g_frags) full.insert(full.end(), f.begin(), f.end());
    payload = full.data();
    paylen = full.size();
    g_frag_active = false;
  }
  if (is_duplicate(hdr.seq, hdr.msg_type, mac)){
    if (!g_last_response.empty()) send_raw(mac, g_last_response);
    return;
  }

  switch (hdr.msg_type){
    case PB_PING: {
      PbHeader resp;
      resp.msg_type = PB_PING_ACK;
      resp.seq = hdr.seq;
      auto frame = pb_build_frame(resp, nullptr, 0);
      send_raw(mac, frame);
      remember(hdr.seq, resp.msg_type, mac, frame);
      break;
    }
    case PB_WRITE_CFG: {
      DynamicJsonDocument doc(1024);
      if (!cbor_decode_to_json(payload, paylen, doc)){ send_nack(mac, hdr.seq, "BAD_REQUEST", "cbor"); break; }
      String token = doc["token"] | "";
      if (token != g_token){
        send_nack(mac, hdr.seq, "SECURITY_DENIED", "token mismatch");
        break;
      }
      JsonObject cfg = doc["cfg"];
      if (cfg.isNull()){ send_nack(mac, hdr.seq, "BAD_REQUEST", "cfg missing"); break; }
      if (cfg.containsKey("wifi")){
        JsonObject w = cfg["wifi"];
        set_pref("wifi_ssid", (const char*)w["ssid"]);
        set_pref("wifi_pass", (const char*)w["pass"]);
        set_pref_int("wifi_dhcp", w["dhcp"] | 1);
      }
      if (cfg.containsKey("mqtt")){
        JsonObject m = cfg["mqtt"];
        set_pref("mqtt_host", (const char*)m["host"]);
        set_pref_int("mqtt_port", m["port"] | 1883);
        set_pref("mqtt_user", (const char*)m["user"]);
        set_pref("mqtt_pass", (const char*)m["pass"]);
        set_pref("mqtt_topic_prefix", (const char*)m["topic_prefix"]);
      }
      if (cfg.containsKey("sys")){
        JsonObject s = cfg["sys"];
        set_pref("sys_timezone", (const char*)s["timezone"]);
        set_pref("sys_log_level", (const char*)s["log_level"]);
      }
      int ver = prefs.getInt("cfg_version", 0) + 1;
      set_pref_int("cfg_version", ver);
      PbHeader resp;
      resp.msg_type = PB_WRITE_ACK;
      resp.seq = hdr.seq;
      auto frame = pb_build_frame(resp, nullptr, 0);
      send_raw(mac, frame);
      remember(hdr.seq, resp.msg_type, mac, frame);
      break;
    }
    case PB_READ_CFG: {
      DynamicJsonDocument req(512);
      if (!cbor_decode_to_json(payload, paylen, req)){ send_nack(mac, hdr.seq, "BAD_REQUEST", "cbor"); break; }
      String token = req["token"] | "";
      if (token != g_token){
        send_nack(mac, hdr.seq, "SECURITY_DENIED", "token mismatch");
        break;
      }
      DynamicJsonDocument out(512);
      JsonObject data = out.createNestedObject("data");
      JsonArray fields = req["fields"].is<JsonArray>() ? req["fields"].as<JsonArray>() : JsonArray();
      auto putField = [&](const char* key, const String& val){
        String k(key);
        if (k.startsWith("wifi.")) {
          JsonObject w = data.containsKey("wifi") ? data["wifi"].as<JsonObject>() : data.createNestedObject("wifi");
          w[k.substring(5)] = val;
        } else if (k.startsWith("mqtt.")){
          JsonObject m = data.containsKey("mqtt") ? data["mqtt"].as<JsonObject>() : data.createNestedObject("mqtt");
          m[k.substring(5)] = val;
        } else if (k.startsWith("sys.")){
          JsonObject s = data.containsKey("sys") ? data["sys"].as<JsonObject>() : data.createNestedObject("sys");
          s[k.substring(4)] = val;
        }
      };
      if (fields){
        for (JsonVariant v : fields){
          String f = v.as<const char*>();
          if (f == "wifi.ssid") putField("wifi.ssid", get_pref("wifi_ssid"));
          if (f == "wifi.pass") putField("wifi.pass", get_pref("wifi_pass"));
          if (f == "mqtt.host") putField("mqtt.host", get_pref("mqtt_host"));
          if (f == "mqtt.port") putField("mqtt.port", String(prefs.getInt("mqtt_port", 1883)));
        }
      }
      auto buf = cbor_encode_json(out.as<JsonVariantConst>());
      PbHeader resp;
      resp.msg_type = PB_READ_ACK;
      resp.seq = hdr.seq;
      resp.payload_len = buf.size();
      auto frame = pb_build_frame(resp, buf.data(), buf.size());
      send_raw(mac, frame);
      remember(hdr.seq, resp.msg_type, mac, frame);
      break;
    }
    case PB_APPLY: {
      // load prefs into runtime (best-effort)
      String ssid = get_pref("wifi_ssid");
      String pass = get_pref("wifi_pass");
      String mqtt_host = get_pref("mqtt_host");
      int mqtt_port = get_pref_int("mqtt_port", 1883);
      if (ssid.length()){
        WiFi.disconnect(true);
        delay(100);
        WiFi.begin(ssid.c_str(), pass.length() ? pass.c_str() : nullptr);
      }
      if (g_mqtt){
        g_mqtt->apply_network_settings(ssid, pass, mqtt_host, mqtt_port);
      }
      PbHeader resp;
      resp.msg_type = PB_APPLY_ACK;
      resp.seq = hdr.seq;
      auto frame = pb_build_frame(resp, nullptr, 0);
      send_raw(mac, frame);
      remember(hdr.seq, resp.msg_type, mac, frame);
      g_cfg_applied = true;
      // Optional: could trigger WiFi/MQTT reconnect here based on prefs
      break;
    }
    case PB_REBOOT: {
      PbHeader resp;
      resp.msg_type = PB_REBOOT_ACK;
      resp.seq = hdr.seq;
      auto frame = pb_build_frame(resp, nullptr, 0);
      send_raw(mac, frame);
      remember(hdr.seq, resp.msg_type, mac, frame);
      delay(200);
      ESP.restart();
      break;
    }
    default:
      send_nack(mac, hdr.seq, "UNSUPPORTED_OP", "not implemented");
      break;
  }
}

void prov_loop(){
  if (g_frag_active && millis() - g_frag_last_ms > 1200){
    g_frag_active = false;
    g_frags.clear();
  }
}
