#pragma once
#include <Arduino.h>
#include <vector>
#include <ArduinoJson.h>

// Minimal CBOR encoder/decoder for strings/ints/bools/maps/arrays used in provisioning.

// Encode a JsonVariant into CBOR bytes.
std::vector<uint8_t> cbor_encode_json(const JsonVariantConst& v);

// Encode token+cfg JSON (cfg_json may be empty -> empty map).
std::vector<uint8_t> cbor_encode_cfg(const String& token, const String& cfg_json);

// Encode token+fields array of strings.
std::vector<uint8_t> cbor_encode_fields(const String& token, const std::vector<String>& fields);

// Decode CBOR bytes into a DynamicJsonDocument root (returns false on error).
bool cbor_decode_to_json(const uint8_t* data, size_t len, DynamicJsonDocument& out);
