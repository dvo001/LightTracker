#include "bridge_ops.h"
#include "job_state.h"
#include "job_executor.h"
#include <ArduinoJson.h>

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

  return make_err(op, id, dev, "UNSUPPORTED_OP", "unknown op");
}
