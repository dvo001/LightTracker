#pragma once
#include <Stream.h>
#include <vector>
#include <functional>
#include <Arduino.h>
#include <cstdio>

#ifndef UWB_ANCHOR_INDEX
#define UWB_ANCHOR_INDEX -1
#endif
#ifndef UWB_TAG_MAC_0
#define UWB_TAG_MAC_0 nullptr
#endif
#ifndef UWB_TAG_MAC_1
#define UWB_TAG_MAC_1 nullptr
#endif
#ifndef UWB_TAG_MAC_2
#define UWB_TAG_MAC_2 nullptr
#endif
#ifndef UWB_TAG_MAC_3
#define UWB_TAG_MAC_3 nullptr
#endif
#ifndef UWB_TAG_MAC_4
#define UWB_TAG_MAC_4 nullptr
#endif
#ifndef UWB_TAG_MAC_5
#define UWB_TAG_MAC_5 nullptr
#endif
#ifndef UWB_TAG_MAC_6
#define UWB_TAG_MAC_6 nullptr
#endif
#ifndef UWB_TAG_MAC_7
#define UWB_TAG_MAC_7 nullptr
#endif

// Minimal AT adapter stub with SIM mode support. Real AT mapping TBD.
class UwbAtAdapter {
public:
  Stream* serial = nullptr;
  int parse_errors = 0;
  using RangeCallback = std::function<void(const String& tag_mac, float d_m)>;
  RangeCallback on_range = nullptr;
  String tag_map[8];

  void begin(Stream& s) {
    serial = &s;
    serial->setTimeout(20);
  }

  void set_tag_mac(int tid, const String& mac) {
    if (tid < 0 || tid >= 8) return;
    tag_map[tid] = mac;
  }

  void poll() {
#ifdef SIM_RANGES
    // no-op; ranges produced by firmware simulation
#else
    if (!serial) return;
    while (serial->available()) {
      String line = serial->readStringUntil('\n');
      line.trim();
      if (!line.length()) continue;
      if (line.indexOf("AT+RANGE") < 0) continue;
      int tid = -1;
      int ranges[8] = {0};
      if (!parse_at_range(line, tid, ranges)) {
        parse_errors++;
        continue;
      }
      int cm = pick_range_cm(ranges);
      if (cm <= 0) continue;
      String tag = tag_name_for_id(tid);
      float d_m = cm / 100.0f;
      if (on_range) on_range(tag, d_m);
    }
#endif
  }

private:
  String tag_name_for_id(int tid) const {
    if (tid >= 0 && tid < 8) {
      if (tag_map[tid].length()) return tag_map[tid];
    }
    const char* mapped = tag_mac_for_id(tid);
    if (mapped) return String(mapped);
    return String("T") + String(tid);
  }

  static const char* tag_mac_for_id(int tid) {
    switch (tid) {
      case 0: return UWB_TAG_MAC_0;
      case 1: return UWB_TAG_MAC_1;
      case 2: return UWB_TAG_MAC_2;
      case 3: return UWB_TAG_MAC_3;
      case 4: return UWB_TAG_MAC_4;
      case 5: return UWB_TAG_MAC_5;
      case 6: return UWB_TAG_MAC_6;
      case 7: return UWB_TAG_MAC_7;
      default: return nullptr;
    }
  }

  static bool parse_at_range(const String& line, int& tid_out, int ranges_out[8]) {
    int tid_pos = line.indexOf("tid:");
    if (tid_pos < 0) return false;
    int tid_end = line.indexOf(",", tid_pos);
    if (tid_end < 0) return false;
    String tid_str = line.substring(tid_pos + 4, tid_end);
    tid_str.trim();
    if (!tid_str.length()) return false;
    tid_out = tid_str.toInt();
    int range_pos = line.indexOf("range:(");
    if (range_pos < 0) return false;
    int range_end = line.indexOf(")", range_pos);
    if (range_end < 0) return false;
    String range_str = line.substring(range_pos, range_end + 1);
    int parsed = sscanf(range_str.c_str(),
                        "range:(%d,%d,%d,%d,%d,%d,%d,%d)",
                        &ranges_out[0], &ranges_out[1], &ranges_out[2], &ranges_out[3],
                        &ranges_out[4], &ranges_out[5], &ranges_out[6], &ranges_out[7]);
    return parsed == 8;
  }

  static int pick_range_cm(const int ranges[8]) {
    if (UWB_ANCHOR_INDEX >= 0 && UWB_ANCHOR_INDEX < 8) {
      return ranges[UWB_ANCHOR_INDEX];
    }
    for (int i = 0; i < 8; i++) {
      if (ranges[i] > 0) return ranges[i];
    }
    return 0;
  }
};
