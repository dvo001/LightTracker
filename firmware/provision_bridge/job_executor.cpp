#include "job_executor.h"
#include <vector>
#include "../common/pb_proto.h"
#include "espnow_link.h"
#include "bridge_rx.h"
#include "../common/cbor_codec.h"

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

static bool validate_common(const DynamicJsonDocument& doc, String& id, String& op, String& dev){
  id = doc["id"] | "";
  op = doc["op"] | "";
  dev = doc["device_id"] | "";
  int v = doc["v"] | 0;
  if (v != 1 || id == "" || op == "" || dev == "") return false;
  return true;
}

static bool parse_mac(const String& mac_str, uint8_t out[6]){
  String s = mac_str;
  s.replace(":", "");
  if (s.length() != 12) return false;
  for (int i = 0; i < 6; i++){
    char buf[3] = { s[2*i], s[2*i+1], 0 };
    out[i] = (uint8_t) strtoul(buf, nullptr, 16);
  }
  return true;
}

static bool send_and_wait(const uint8_t* mac, PbMsgType type, const std::vector<uint8_t>& payload, uint16_t seq, uint8_t expect_type, uint32_t timeout_ms, int retries, String& err_code, RxState* rx_out=nullptr){
  // fragment if needed
  size_t total = payload.size();
  size_t frag_cnt = (total + PB_MAX_PAYLOAD_PER_FRAME - 1) / PB_MAX_PAYLOAD_PER_FRAME;
  if (frag_cnt == 0) frag_cnt = 1;
  for (int attempt = 0; attempt < retries; attempt++){
    bool tx_ok = true;
    for (size_t i=0; i<frag_cnt; i++){
      size_t offset = i * PB_MAX_PAYLOAD_PER_FRAME;
      size_t len = min((size_t)PB_MAX_PAYLOAD_PER_FRAME, total - offset);
      PbHeader hdr;
      hdr.msg_type = type;
      hdr.seq = seq;
      hdr.flags = (frag_cnt > 1 ? PB_FLAG_IS_FRAG : 0);
      if (frag_cnt > 1 && i == frag_cnt-1) hdr.flags |= PB_FLAG_LAST_FRAG;
      hdr.frag_idx = i;
      hdr.frag_cnt = frag_cnt;
      hdr.payload_len = len;
      const uint8_t* ptr = len ? payload.data() + offset : nullptr;
      auto frame = pb_build_frame(hdr, ptr, len);
      if (!espnow_send_frame(mac, frame.data(), frame.size())){
        tx_ok = false;
        break;
      }
      delay(5); // pacing
    }
    if (!tx_ok){
      err_code = "PROPRIETARY_TX_FAIL";
      continue;
    }
    RxState rx;
    if (bridge_rx_wait(seq, expect_type, mac, timeout_ms, rx)){
      if (rx.hdr.msg_type == PB_NACK){
        err_code = "NACK";
        return false;
      }
      if (rx_out) *rx_out = rx;
      return true;
    }
    err_code = "NO_ACK";
  }
  return false;
}

String handle_provision_write(const DynamicJsonDocument& doc, JobState& job){
  String id, op, dev;
  if (!validate_common(doc, id, op, dev)){
    return "{\"v\":1,\"status\":\"error\",\"err\":{\"code\":\"BAD_REQUEST\"}}";
  }
  if (job.status == JobStatus::BUSY){
    return make_err(op, id, dev, "BUSY", "bridge busy");
  }
  uint8_t mac[6];
  if (!parse_mac(dev, mac)) return make_err(op, id, dev, "BAD_REQUEST", "invalid mac");
  String token = doc["auth"]["token"] | "";
  if (token == "") return make_err(op, id, dev, "SECURITY_DENIED", "token required");
  String cfg_json;
  serializeJson(doc["cfg"], cfg_json);
  auto payload = cbor_encode_cfg(token, cfg_json);

  job.status = JobStatus::BUSY;
  job.current_id = id;
  memcpy(job.current_mac.data(), mac, 6);
  uint16_t seq = job.next_seq();
  String err;
  bool ok = send_and_wait(mac, PB_WRITE_CFG, payload, seq, PB_WRITE_ACK, doc["timeout_ms"] | 8000, 3, err);
  if (ok && (bool)(doc["apply"] | false)){
    ok = send_and_wait(mac, PB_APPLY, {}, seq, PB_APPLY_ACK, doc["timeout_ms"] | 3000, 2, err);
  }
  if (ok && (bool)(doc["reboot"] | false)){
    ok = send_and_wait(mac, PB_REBOOT, {}, seq, PB_REBOOT_ACK, doc["timeout_ms"] | 4000, 2, err);
  }
  job.clear();

  if (!ok){
    return make_err(op, id, dev, err.c_str(), "provision_write failed");
  }
  DynamicJsonDocument resp(128);
  resp["v"] = 1;
  resp["id"] = id;
  resp["op"] = "provision_write_ack";
  resp["device_id"] = dev;
  resp["status"] = "ok";
  resp["detail"] = "stored";
  String out; serializeJson(resp, out); return out;
}

String handle_provision_read(const DynamicJsonDocument& doc, JobState& job){
  String id, op, dev;
  if (!validate_common(doc, id, op, dev)){
    return "{\"v\":1,\"status\":\"error\",\"err\":{\"code\":\"BAD_REQUEST\"}}";
  }
  if (job.status == JobStatus::BUSY){
    return make_err(op, id, dev, "BUSY", "bridge busy");
  }
  uint8_t mac[6];
  if (!parse_mac(dev, mac)) return make_err(op, id, dev, "BAD_REQUEST", "invalid mac");
  String token = doc["auth"]["token"] | "";
  if (token == "") return make_err(op, id, dev, "SECURITY_DENIED", "token required");
  std::vector<String> fields;
  JsonArrayConst arr = doc["fields"].as<JsonArrayConst>();
  if (!arr.isNull()){
    for (JsonVariantConst v : arr){
      fields.push_back((String)v.as<const char*>());
    }
  }
  auto payload = cbor_encode_fields(token, fields);

  job.status = JobStatus::BUSY;
  job.current_id = id;
  memcpy(job.current_mac.data(), mac, 6);
  uint16_t seq = job.next_seq();
  String err;
  RxState rx;
  bool ok = send_and_wait(mac, PB_READ_CFG, payload, seq, PB_READ_ACK, doc["timeout_ms"] | 5000, 2, err, &rx);
  job.clear();
  if (!ok){
    return make_err(op, id, dev, err.c_str(), "provision_read failed");
  }
  DynamicJsonDocument resp(256);
  resp["v"] = 1;
  resp["id"] = id;
  resp["op"] = "provision_read_ack";
  resp["device_id"] = dev;
  resp["status"] = "ok";
  // decode MsgPack/CBOR data
  DynamicJsonDocument dataDoc(512);
  cbor_decode_to_json(rx.payload.data(), rx.payload.size(), dataDoc);
  resp["data"] = dataDoc["data"];
  String out; serializeJson(resp, out); return out;
}

String handle_reboot(const DynamicJsonDocument& doc, JobState& job){
  String id, op, dev;
  if (!validate_common(doc, id, op, dev)){
    return "{\"v\":1,\"status\":\"error\",\"err\":{\"code\":\"BAD_REQUEST\"}}";
  }
  if (job.status == JobStatus::BUSY){
    return make_err(op, id, dev, "BUSY", "bridge busy");
  }
  uint8_t mac[6];
  if (!parse_mac(dev, mac)) return make_err(op, id, dev, "BAD_REQUEST", "invalid mac");
  job.status = JobStatus::BUSY;
  job.current_id = id;
  memcpy(job.current_mac.data(), mac, 6);
  uint16_t seq = job.next_seq();
  String err;
  bool ok = send_and_wait(mac, PB_REBOOT, {}, seq, PB_REBOOT_ACK, doc["timeout_ms"] | 4000, 2, err);
  job.clear();
  if (!ok) return make_err(op, id, dev, err.c_str(), "reboot failed");
  DynamicJsonDocument resp(128);
  resp["v"] = 1;
  resp["id"] = id;
  resp["op"] = "reboot_ack";
  resp["device_id"] = dev;
  resp["status"] = "ok";
  String out; serializeJson(resp, out); return out;
}
