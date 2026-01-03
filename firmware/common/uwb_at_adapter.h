#pragma once
#include <Stream.h>
#include <vector>
#include <functional>
#include <Arduino.h>

// Minimal AT adapter stub with SIM mode support. Real AT mapping TBD.
class UwbAtAdapter {
public:
  Stream* serial = nullptr;
  int parse_errors = 0;
  using RangeCallback = std::function<void(const String& tag_mac, float d_m)>;
  RangeCallback on_range = nullptr;

  void begin(Stream& s) { serial = &s; }

  void poll() {
#ifdef SIM_RANGES
    // no-op; ranges produced by firmware simulation
#else
    if (!serial) return;
    while (serial->available()) {
      String line = serial->readStringUntil('\n');
      // naive parser: if line contains "RANGE" parse tag,d
      if (line.indexOf("RANGE") >= 0) {
        // expected: RANGE TAG:11:22.. D:1.234
        int p = line.indexOf("TAG:");
        int q = line.indexOf("D:");
        if (p >= 0 && q >= 0) {
          String tag = line.substring(p + 4, q);
          tag.trim();
          String d = line.substring(q + 2);
          d.trim();
          float dv = d.toFloat();
          if (on_range) on_range(tag, dv);
        } else {
          parse_errors++;
        }
      }
    }
#endif
  }
};
