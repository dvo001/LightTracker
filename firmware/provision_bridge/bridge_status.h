#pragma once

#include <Arduino.h>
#include <stdint.h>

struct BridgeStatusSnapshot {
  bool dmx_seen = false;
  bool dmx_ok = false;
  uint32_t dmx_last_ms = 0;

  bool espnow_seen = false;
  bool espnow_ok = false;
  uint32_t espnow_last_ms = 0;
};

void bridge_status_reset();
void bridge_status_mark_dmx(bool ok);
void bridge_status_mark_espnow(bool ok);
BridgeStatusSnapshot bridge_status_snapshot();
