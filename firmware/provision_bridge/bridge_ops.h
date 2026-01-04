#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>

// Handle a parsed NDJSON message and return a response line (or empty if none).
String bridge_handle_msg(const DynamicJsonDocument& doc);
