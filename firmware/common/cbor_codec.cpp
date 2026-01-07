#include "cbor_codec.h"

static void cbor_put_uint(std::vector<uint8_t>& out, uint8_t major, uint64_t val){
  if (val < 24){
    out.push_back((major<<5) | val);
  } else if (val <= 0xFF){
    out.push_back((major<<5) | 24);
    out.push_back((uint8_t)val);
  } else if (val <= 0xFFFF){
    out.push_back((major<<5) | 25);
    out.push_back((val>>8)&0xFF);
    out.push_back(val&0xFF);
  } else {
    out.push_back((major<<5) | 26);
    out.push_back((val>>24)&0xFF);
    out.push_back((val>>16)&0xFF);
    out.push_back((val>>8)&0xFF);
    out.push_back(val&0xFF);
  }
}

static void cbor_encode_variant(std::vector<uint8_t>& out, const JsonVariantConst& v){
  if (v.isNull()){
    out.push_back(0xF6); // null
    return;
  }
  if (v.is<bool>()){
    out.push_back(v.as<bool>() ? 0xF5 : 0xF4);
    return;
  }
  if (v.is<int>() || v.is<long>() || v.is<long long>() || v.is<unsigned long>() || v.is<unsigned long long>()){
    int64_t n = v.as<long long>();
    if (n >= 0) cbor_put_uint(out, 0, (uint64_t)n);
    else { // negative
      uint64_t m = (uint64_t)(-1 - n);
      cbor_put_uint(out, 1, m);
    }
    return;
  }
  if (v.is<const char*>() || v.is<String>()){
    String s = v.as<String>();
    cbor_put_uint(out, 3, s.length());
    for (size_t i=0;i<s.length();i++) out.push_back((uint8_t)s[i]);
    return;
  }
  if (v.is<JsonArrayConst>()){
    JsonArrayConst arr = v.as<JsonArrayConst>();
    cbor_put_uint(out, 4, arr.size());
    for (JsonVariantConst it : arr) cbor_encode_variant(out, it);
    return;
  }
  if (v.is<JsonObjectConst>()){
    JsonObjectConst obj = v.as<JsonObjectConst>();
    cbor_put_uint(out, 5, obj.size());
    for (JsonPairConst kv : obj){
      String key = kv.key().c_str();
      cbor_put_uint(out, 3, key.length());
      for (size_t i=0;i<key.length();i++) out.push_back((uint8_t)key[i]);
      cbor_encode_variant(out, kv.value());
    }
    return;
  }
  // fallback: null
  out.push_back(0xF6);
}

std::vector<uint8_t> cbor_encode_json(const JsonVariantConst& v){
  std::vector<uint8_t> out;
  cbor_encode_variant(out, v);
  return out;
}

std::vector<uint8_t> cbor_encode_cfg(const String& token, const String& cfg_json){
  DynamicJsonDocument doc(1024);
  DynamicJsonDocument cfg(1024);
  if (cfg_json.length()) deserializeJson(cfg, cfg_json);
  doc["token"] = token;
  doc["cfg"] = cfg.as<JsonVariant>();
  return cbor_encode_json(doc.as<JsonVariantConst>());
}

std::vector<uint8_t> cbor_encode_fields(const String& token, const std::vector<String>& fields){
  DynamicJsonDocument doc(512);
  doc["token"] = token;
  JsonArray arr = doc.createNestedArray("fields");
  for (auto& f : fields) arr.add(f);
  return cbor_encode_json(doc.as<JsonVariantConst>());
}

// CBOR decoder (minimal, supports unsigned/signed int, text, map, array, bool/null)
struct CborView {
  const uint8_t* start;
  const uint8_t* p;
  const uint8_t* end;
};

static bool cbor_fail(CborView& cv, const char* msg, uint8_t ib=0){
  uint32_t off = (uint32_t)(cv.p - cv.start);
  if (ib){
    Serial.printf("cbor: fail %s off=%u ib=0x%02X maj=%u ai=%u\n",
                  msg, off, ib, (unsigned)(ib >> 5), (unsigned)(ib & 0x1F));
  } else {
    Serial.printf("cbor: fail %s off=%u\n", msg, off);
  }
  return false;
}

static bool cbor_read_len(CborView& cv, uint8_t ai, uint64_t& len){
  if (ai < 24){ len = ai; return true; }
  if (ai == 24){
    if (cv.p >= cv.end) return cbor_fail(cv, "len8-oob");
    len = *cv.p++;
    return true;
  }
  if (ai == 25){
    if (cv.p+1 >= cv.end) return cbor_fail(cv, "len16-oob");
    len = (cv.p[0]<<8)|cv.p[1];
    cv.p+=2;
    return true;
  }
  if (ai == 26){
    if (cv.p+3 >= cv.end) return cbor_fail(cv, "len32-oob");
    len = ((uint32_t)cv.p[0]<<24)|((uint32_t)cv.p[1]<<16)|((uint32_t)cv.p[2]<<8)|cv.p[3];
    cv.p+=4;
    return true;
  }
  return cbor_fail(cv, "len-unsupported");
}

static bool cbor_to_json(CborView& cv, JsonVariant out){
  if (cv.p >= cv.end) return cbor_fail(cv, "eof");
  uint8_t ib = *cv.p++;
  uint8_t maj = ib >> 5;
  uint8_t ai = ib & 0x1F;
  uint64_t val = 0;
  switch (maj){
    case 0: { // unsigned
      if (!cbor_read_len(cv, ai, val)) return false;
      out.set(val);
      return true;
    }
    case 1: { // negative
      if (!cbor_read_len(cv, ai, val)) return false;
      int64_t n = -1 - (int64_t)val;
      out.set(n);
      return true;
    }
    case 3: { // text
      if (!cbor_read_len(cv, ai, val)) return false;
      if (cv.p + val > cv.end) return cbor_fail(cv, "text-oob", ib);
      String s;
      s.reserve(val);
      for (uint64_t i=0;i<val;i++) s += (char)cv.p[i];
      cv.p += val;
      out.set(s);
      return true;
    }
    case 4: { // array
      if (!cbor_read_len(cv, ai, val)) return false;
      JsonArray arr = out.to<JsonArray>();
      if (arr.isNull()) return cbor_fail(cv, "array-alloc", ib);
      for (uint64_t i=0;i<val;i++){
        JsonVariant v = arr.add();
        if (v.isNull()) return cbor_fail(cv, "array-add", ib);
        if (!cbor_to_json(cv, v)) return false;
      }
      return true;
    }
    case 5: { // map
      if (!cbor_read_len(cv, ai, val)) return false;
      JsonObject obj = out.to<JsonObject>();
      if (obj.isNull()) return cbor_fail(cv, "map-alloc", ib);
      for (uint64_t i=0;i<val;i++){
        if (cv.p >= cv.end) return cbor_fail(cv, "map-key-eof");
        uint8_t kb = *cv.p++;
        if ((kb>>5)!=3) return cbor_fail(cv, "map-key-type", kb);
        uint64_t klen=0;
        if (!cbor_read_len(cv, kb&0x1F, klen)) return false;
        if (cv.p + klen > cv.end) return cbor_fail(cv, "map-key-oob", kb);
        String key;
        key.reserve(klen);
        for (uint64_t j=0;j<klen;j++) key += (char)cv.p[j];
        cv.p += klen;
        JsonVariant v = obj[key];
        if (!cbor_to_json(cv, v)) return false;
      }
      return true;
    }
    case 7: { // simple
      if (ai == 20){ out.set(false); return true; }
      if (ai == 21){ out.set(true); return true; }
      if (ai == 22 || ai==23){ out.set(nullptr); return true; }
      return cbor_fail(cv, "simple-unsupported", ib);
    }
    default:
      return cbor_fail(cv, "maj-unsupported", ib);
  }
}

bool cbor_decode_to_json(const uint8_t* data, size_t len, DynamicJsonDocument& out){
  CborView cv{data, data, data+len};
  return cbor_to_json(cv, out.to<JsonVariant>());
}
