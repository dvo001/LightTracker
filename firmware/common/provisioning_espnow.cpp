#include "provisioning_espnow.h"
#include <esp_wifi.h>
#include <esp_now.h>
#include <Preferences.h>
#include "pb_proto.h"
#include <ArduinoJson.h>
#include "mqtt_client.h"
#include "cbor_codec.h"
#include <nvs_flash.h>

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
static void on_recv(const uint8_t *mac, const uint8_t *data, int len);
static bool g_active = false;

struct CborView {
  const uint8_t* p;
  const uint8_t* end;
};

struct CborCfgOut {
  String token;
  String wifi_ssid;
  String wifi_pass;
  int wifi_dhcp = 1;
  String mqtt_host;
  int mqtt_port = 1883;
  String mqtt_user;
  String mqtt_pass;
  String mqtt_topic;
  bool has_wifi = false;
  bool has_mqtt = false;
  bool has_wifi_ssid = false;
  bool has_wifi_pass = false;
  bool has_wifi_dhcp = false;
  bool has_mqtt_host = false;
  bool has_mqtt_port = false;
  bool has_mqtt_user = false;
  bool has_mqtt_pass = false;
  bool has_mqtt_topic = false;
};

static bool cbor_read_len(CborView& cv, uint8_t ai, uint64_t& len){
  if (ai < 24){ len = ai; return true; }
  if (ai == 24){
    if (cv.p >= cv.end) return false;
    len = *cv.p++;
    return true;
  }
  if (ai == 25){
    if (cv.p + 1 >= cv.end) return false;
    len = (cv.p[0] << 8) | cv.p[1];
    cv.p += 2;
    return true;
  }
  if (ai == 26){
    if (cv.p + 3 >= cv.end) return false;
    len = ((uint32_t)cv.p[0] << 24) | ((uint32_t)cv.p[1] << 16) | ((uint32_t)cv.p[2] << 8) | cv.p[3];
    cv.p += 4;
    return true;
  }
  return false;
}

static bool cbor_read_head(CborView& cv, uint8_t& maj, uint64_t& val){
  if (cv.p >= cv.end) return false;
  uint8_t ib = *cv.p++;
  maj = ib >> 5;
  uint8_t ai = ib & 0x1F;
  if (maj == 7){
    if (ai < 24){ val = ai; return true; }
    return false;
  }
  return cbor_read_len(cv, ai, val);
}

static bool cbor_read_text(CborView& cv, String& out){
  uint8_t maj = 0;
  uint64_t len = 0;
  if (!cbor_read_head(cv, maj, len)) return false;
  if (maj != 3) return false;
  if (cv.p + len > cv.end) return false;
  out = "";
  out.reserve(len);
  for (uint64_t i = 0; i < len; i++) out += (char)cv.p[i];
  cv.p += len;
  return true;
}

static bool cbor_read_uint(CborView& cv, uint64_t& out){
  uint8_t maj = 0;
  uint64_t val = 0;
  if (!cbor_read_head(cv, maj, val)) return false;
  if (maj != 0) return false;
  out = val;
  return true;
}

static bool cbor_skip(CborView& cv);

static bool cbor_skip_value(CborView& cv, uint8_t maj, uint64_t val){
  switch (maj){
    case 0:
    case 1:
      return true;
    case 2:
    case 3:
      if (cv.p + val > cv.end) return false;
      cv.p += val;
      return true;
    case 4:
      for (uint64_t i = 0; i < val; i++){
        if (!cbor_skip(cv)) return false;
      }
      return true;
    case 5:
      for (uint64_t i = 0; i < val; i++){
        if (!cbor_skip(cv)) return false;
        if (!cbor_skip(cv)) return false;
      }
      return true;
    case 7:
      return true;
    default:
      return false;
  }
}

static bool cbor_skip(CborView& cv){
  uint8_t maj = 0;
  uint64_t val = 0;
  if (!cbor_read_head(cv, maj, val)) return false;
  return cbor_skip_value(cv, maj, val);
}

static bool cbor_parse_wifi_map(CborView& cv, CborCfgOut& out){
  uint8_t maj = 0;
  uint64_t count = 0;
  if (!cbor_read_head(cv, maj, count)) return false;
  if (maj != 5) return cbor_skip_value(cv, maj, count);
  out.has_wifi = true;
  for (uint64_t i = 0; i < count; i++){
    String key;
    if (!cbor_read_text(cv, key)) return false;
    if (key == "ssid"){
      String val;
      if (!cbor_read_text(cv, val)) return false;
      out.wifi_ssid = val;
      out.has_wifi_ssid = true;
    } else if (key == "pass"){
      String val;
      if (!cbor_read_text(cv, val)) return false;
      out.wifi_pass = val;
      out.has_wifi_pass = true;
    } else if (key == "dhcp"){
      uint64_t v = 0;
      if (!cbor_read_uint(cv, v)) return false;
      out.wifi_dhcp = (int)v;
      out.has_wifi_dhcp = true;
    } else {
      if (!cbor_skip(cv)) return false;
    }
  }
  return true;
}

static bool cbor_parse_mqtt_map(CborView& cv, CborCfgOut& out){
  uint8_t maj = 0;
  uint64_t count = 0;
  if (!cbor_read_head(cv, maj, count)) return false;
  if (maj != 5) return cbor_skip_value(cv, maj, count);
  out.has_mqtt = true;
  for (uint64_t i = 0; i < count; i++){
    String key;
    if (!cbor_read_text(cv, key)) return false;
    if (key == "host"){
      String val;
      if (!cbor_read_text(cv, val)) return false;
      out.mqtt_host = val;
      out.has_mqtt_host = true;
    } else if (key == "port"){
      uint64_t v = 0;
      if (!cbor_read_uint(cv, v)) return false;
      out.mqtt_port = (int)v;
      out.has_mqtt_port = true;
    } else if (key == "user"){
      String val;
      if (!cbor_read_text(cv, val)) return false;
      out.mqtt_user = val;
      out.has_mqtt_user = true;
    } else if (key == "pass"){
      String val;
      if (!cbor_read_text(cv, val)) return false;
      out.mqtt_pass = val;
      out.has_mqtt_pass = true;
    } else if (key == "topic_prefix"){
      String val;
      if (!cbor_read_text(cv, val)) return false;
      out.mqtt_topic = val;
      out.has_mqtt_topic = true;
    } else {
      if (!cbor_skip(cv)) return false;
    }
  }
  return true;
}

static bool cbor_parse_cfg_map(CborView& cv, CborCfgOut& out){
  uint8_t maj = 0;
  uint64_t count = 0;
  if (!cbor_read_head(cv, maj, count)) return false;
  if (maj != 5) return cbor_skip_value(cv, maj, count);
  for (uint64_t i = 0; i < count; i++){
    String key;
    if (!cbor_read_text(cv, key)) return false;
    if (key == "wifi"){
      if (!cbor_parse_wifi_map(cv, out)) return false;
    } else if (key == "mqtt"){
      if (!cbor_parse_mqtt_map(cv, out)) return false;
    } else {
      if (!cbor_skip(cv)) return false;
    }
  }
  return true;
}

static bool cbor_decode_cfg(const uint8_t* data, size_t len, CborCfgOut& out){
  CborView cv{data, data + len};
  uint8_t maj = 0;
  uint64_t count = 0;
  if (!cbor_read_head(cv, maj, count)) return false;
  if (maj != 5) return false;
  for (uint64_t i = 0; i < count; i++){
    String key;
    if (!cbor_read_text(cv, key)) return false;
    if (key == "token"){
      String val;
      if (!cbor_read_text(cv, val)) return false;
      out.token = val;
    } else if (key == "cfg"){
      if (!cbor_parse_cfg_map(cv, out)) return false;
    } else {
      if (!cbor_skip(cv)) return false;
    }
  }
  return true;
}

static String get_pref(const char* key, const String& def=""){
  if (!prefs.isKey(key)) return def;
  return prefs.getString(key, def);
}
static void set_pref(const char* key, const String& val){ prefs.putString(key, val); }
static void set_pref_int(const char* key, int v){ prefs.putInt(key, v); }
static int get_pref_int(const char* key, int defv){
  if (!prefs.isKey(key)) return defv;
  return prefs.getInt(key, defv);
}

static PiMqttClient* g_mqtt = nullptr;
static void mirror_to_lt_cfg(){
  Preferences cfg;
  if (!cfg.begin("lt_cfg", false)){
    Serial.println("prov: lt_cfg open failed");
    return;
  }
  cfg.putString("ssid", get_pref("wifi_ssid"));
  cfg.putString("pass", get_pref("wifi_pass"));
  cfg.putString("mqtt_host", get_pref("mqtt_host"));
  cfg.putInt("mqtt_port", get_pref_int("mqtt_port", 1883));
  cfg.end();
  Serial.printf("prov: mirrored lt_cfg ssid='%s' pass_len=%d mqtt_host='%s' mqtt_port=%d\n",
                get_pref("wifi_ssid").c_str(),
                (int)get_pref("wifi_pass").length(),
                get_pref("mqtt_host").c_str(),
                get_pref_int("mqtt_port", 1883));
}

void prov_init(){
  g_active = false;
  // ensure ESP-NOW uses a known channel and WiFi STA is idle
  WiFi.disconnect(true, true);
  delay(50);
  WiFi.mode(WIFI_STA);
  esp_wifi_set_channel(6, WIFI_SECOND_CHAN_NONE);
  if (esp_now_init() != ESP_OK){
    Serial.println("prov: esp_now_init failed");
    return;
  }
  if (esp_now_register_recv_cb(on_recv) != ESP_OK){
    Serial.println("prov: register_recv failed");
    return;
  }
  g_active = true;
  Serial.println("prov: espnow active on channel 6");
  if (!prefs.begin("prov", false)){
    Serial.println("prov: prefs open failed, reinit NVS");
    nvs_flash_erase();
    nvs_flash_init();
    prefs.begin("prov", false);
  }
  // debug: show stored config
  Serial.printf("prov: stored ssid='%s' pass_len=%d mqtt_host='%s' mqtt_port=%d\n",
                get_pref("wifi_ssid").c_str(),
                (int)get_pref("wifi_pass").length(),
                get_pref("mqtt_host").c_str(),
                get_pref_int("mqtt_port", 0));
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
  esp_err_t add = esp_now_add_peer(&peer);
  if (add != ESP_OK){
    Serial.printf("prov: add_peer failed err=%d\n", add);
    return;
  }
  esp_err_t err = esp_now_send(peer.peer_addr, data.data(), data.size());
  if (err != ESP_OK){
    Serial.printf("prov: send fail err=%d len=%u to %02X:%02X:%02X:%02X:%02X:%02X\n",
                  err, (unsigned)data.size(),
                  dest[0], dest[1], dest[2], dest[3], dest[4], dest[5]);
  }
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
  if (!pb_parse_header(data, len, hdr)){
    Serial.printf("prov: parse fail len=%d data=", len);
    int dump = min(len, 16);
    for (int i=0;i<dump;i++){
      Serial.printf("%02X ", data[i]);
    }
    Serial.println();
    return;
  }
  const uint8_t* payload = data + PB_HDR_SIZE;
  size_t paylen = len - PB_HDR_SIZE;
  Serial.printf("prov: rx mac=%02X:%02X:%02X:%02X:%02X:%02X type=%u seq=%u len=%d\n",
                mac[0], mac[1], mac[2], mac[3], mac[4], mac[5],
                hdr.msg_type, hdr.seq, len);
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
      uint16_t payload_crc = pb_crc16(payload, paylen);
      Serial.printf("prov: payload len=%u crc=0x%04X\n", (unsigned)paylen, payload_crc);
      Serial.print("prov: payload hex=");
      for (size_t i = 0; i < paylen; i++){
        Serial.printf("%02X ", payload[i]);
      }
      Serial.println();
      CborCfgOut cfg;
      if (!cbor_decode_cfg(payload, paylen, cfg)){
        Serial.println("prov: cbor decode failed");
        send_nack(mac, hdr.seq, "BAD_REQUEST", "cbor");
        break;
      }
      Serial.printf("prov: decoded token_len=%d has_wifi=%d has_mqtt=%d\n",
                    cfg.token.length(),
                    cfg.has_wifi ? 1 : 0,
                    cfg.has_mqtt ? 1 : 0);
      if (cfg.token != g_token){
        Serial.println("prov: token mismatch");
        send_nack(mac, hdr.seq, "SECURITY_DENIED", "token mismatch");
        break;
      }
      if (cfg.has_wifi){
        if (cfg.has_wifi_ssid) set_pref("wifi_ssid", cfg.wifi_ssid);
        if (cfg.has_wifi_pass || cfg.has_wifi_ssid) set_pref("wifi_pass", cfg.wifi_pass);
        if (cfg.has_wifi_dhcp) set_pref_int("wifi_dhcp", cfg.wifi_dhcp);
        Serial.printf("prov: stored wifi ssid='%s' pass_len=%d dhcp=%d\n",
                      get_pref("wifi_ssid").c_str(),
                      (int)get_pref("wifi_pass").length(),
                      get_pref_int("wifi_dhcp",1));
      }
      if (cfg.has_mqtt){
        if (cfg.has_mqtt_host) set_pref("mqtt_host", cfg.mqtt_host);
        if (cfg.has_mqtt_port) set_pref_int("mqtt_port", cfg.mqtt_port);
        if (cfg.has_mqtt_user) set_pref("mqtt_user", cfg.mqtt_user);
        if (cfg.has_mqtt_pass) set_pref("mqtt_pass", cfg.mqtt_pass);
        if (cfg.has_mqtt_topic) set_pref("mqtt_topic_prefix", cfg.mqtt_topic);
        Serial.printf("prov: stored mqtt host='%s' port=%d user_len=%d pass_len=%d\n",
                      get_pref("mqtt_host").c_str(),
                      get_pref_int("mqtt_port",0),
                      (int)get_pref("mqtt_user").length(),
                      (int)get_pref("mqtt_pass").length());
      }
      int ver = prefs.getInt("cfg_version", 0) + 1;
      set_pref_int("cfg_version", ver);
      mirror_to_lt_cfg();
      PbHeader resp;
      resp.msg_type = PB_WRITE_ACK;
      resp.seq = hdr.seq;
      auto frame = pb_build_frame(resp, nullptr, 0);
      Serial.println("prov: sending write ack");
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
      // send ACK immediately, keep channel stable
      PbHeader resp;
      resp.msg_type = PB_APPLY_ACK;
      resp.seq = hdr.seq;
      auto frame = pb_build_frame(resp, nullptr, 0);
      send_raw(mac, frame);
      remember(hdr.seq, resp.msg_type, mac, frame);
      g_cfg_applied = true;
      // apply on next reboot to avoid channel changes mid-session
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

bool prov_is_active(){
  return g_active;
}
