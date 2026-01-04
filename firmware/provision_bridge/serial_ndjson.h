#pragma once
#include <Arduino.h>

// NDJSON reader/writer (max line 4096, strict JSON).
// Uses ArduinoJson for parsing and forwards parsed objects to a handler callback.
#include <functional>
#include <ArduinoJson.h>

class SerialNdjson {
public:
  using Handler = std::function<void(const DynamicJsonDocument&)>;

  void begin(Stream* s, Handler h){ stream = s; handler = h; }
  void loop();
  void send_line(const String& line);
private:
  Stream* stream = nullptr;
  String buf;
  Handler handler;
};
