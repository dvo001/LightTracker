#include "bridge_ops.h"
#include "job_state.h"
#include "job_executor.h"
#include "dmx_tx.h"
#include "bridge_status.h"
#include <ArduinoJson.h>
#include <mbedtls/base64.h>
#include <cstring>
#include <vector>

extern JobState g_job;

static String make_err(const String& op, const String& id, const String& dev, const char* code, const char* msg){
  DynamicJsonDocument doc(256);
  doc["v"] = 1;
  doc["id"] = id;
  doc["op"] = op + "_ack";
  if (dev.length()) doc["device_id"] = dev;
  doc["status"] = "error";
  JsonObject e = doc.createNestedObject("err");
  e["code"] = code;
  e["msg"] = msg;
  String out; serializeJson(doc, out); return out;
}

static String handle_dmx_write(const DynamicJsonDocument& doc){
  String id = doc["id"] | "";
  String op = doc["op"] | "";
  int universe = doc["universe"] | 0;
  if (id == "" || op == ""){
    return "{\"v\":1,\"status\":\"error\",\"err\":{\"code\":\"BAD_REQUEST\"}}";
  }

  String b64 = doc["frame_b64"] | "";
  if (b64.length() == 0){
    return make_err(op, id, "", "BAD_REQUEST", "frame_b64 required");
  }

  size_t decoded_len = 0;
  int rc = mbedtls_base64_decode(
      nullptr,
      0,
      &decoded_len,
      reinterpret_cast<const unsigned char*>(b64.c_str()),
      b64.length()
  );
  if (!(rc == 0 || rc == MBEDTLS_ERR_BASE64_BUFFER_TOO_SMALL)){
    return make_err(op, id, "", "BAD_FRAME", "base64 probe failed");
  }
  if (decoded_len == 0 || decoded_len > 1024){
    return make_err(op, id, "", "BAD_FRAME", "frame size invalid");
  }

  std::vector<uint8_t> decoded(decoded_len);
  size_t out_len = 0;
  rc = mbedtls_base64_decode(
      decoded.data(),
      decoded.size(),
      &out_len,
      reinterpret_cast<const unsigned char*>(b64.c_str()),
      b64.length()
  );
  if (rc != 0){
    return make_err(op, id, "", "BAD_FRAME", "base64 decode failed");
  }
  decoded.resize(out_len);

  uint8_t frame[513];
  if (decoded.size() == 512){
    frame[0] = 0;
    memcpy(frame + 1, decoded.data(), 512);
  } else if (decoded.size() == 513){
    memcpy(frame, decoded.data(), 513);
  } else {
    return make_err(op, id, "", "BAD_FRAME", "frame must be 512 or 513 bytes");
  }

  if (!dmx_tx_send_frame(frame, sizeof(frame))){
    bridge_status_mark_dmx(false);
    return make_err(op, id, "", "DMX_TX_FAIL", dmx_tx_last_error());
  }
  bridge_status_mark_dmx(true);

  DynamicJsonDocument resp(192);
  resp["v"] = 1;
  resp["id"] = id;
  resp["op"] = "dmx_write_ack";
  resp["status"] = "ok";
  resp["universe"] = universe;
  resp["tx_pin"] = dmx_tx_pin();
  resp["rx_pin"] = dmx_rx_pin();
  String out; serializeJson(resp, out); return out;
}

String bridge_handle_msg(const DynamicJsonDocument& doc){
  int v = doc["v"] | 0;
  String id = doc["id"] | "";
  String op = doc["op"] | "";
  String dev = doc["device_id"] | "";
  if (v != 1 || id == "" || op == "") return "";

  if (op == "hello"){
    DynamicJsonDocument resp(256);
    resp["v"] = 1;
    resp["id"] = id;
    resp["op"] = "hello_ack";
    resp["bridge"] = "prov-esp32";
    resp["fw"] = "0.0.1";
    resp["serial"] = String((uint32_t)ESP.getEfuseMac(), HEX);
    JsonArray cap = resp.createNestedArray("cap");
    cap.add("provision");
    cap.add("readback");
    cap.add("reboot");
    cap.add("dmx_write");
    resp["status"] = "ok";
    String out; serializeJson(resp, out); return out;
  }

  if (g_job.status == JobStatus::BUSY){
    return make_err(op, id, dev, "BUSY", "bridge busy");
  }

  if (op == "provision_write") {
    Serial.printf("bridge: provision_write id=%s dev=%s\n", id.c_str(), dev.c_str());
    return handle_provision_write(doc, g_job);
  }
  if (op == "provision_read") return handle_provision_read(doc, g_job);
  if (op == "reboot") return handle_reboot(doc, g_job);
  if (op == "ping") return handle_ping(doc, g_job);
  if (op == "dmx_write") return handle_dmx_write(doc);

  return make_err(op, id, dev, "UNSUPPORTED_OP", "unknown op");
}
