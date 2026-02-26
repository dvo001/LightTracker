#include "bridge_status.h"

namespace {
BridgeStatusSnapshot g_status;
}

void bridge_status_reset() {
  g_status = BridgeStatusSnapshot{};
}

void bridge_status_mark_dmx(bool ok) {
  g_status.dmx_seen = true;
  g_status.dmx_ok = ok;
  g_status.dmx_last_ms = millis();
}

void bridge_status_mark_espnow(bool ok) {
  g_status.espnow_seen = true;
  g_status.espnow_ok = ok;
  g_status.espnow_last_ms = millis();
}

BridgeStatusSnapshot bridge_status_snapshot() {
  return g_status;
}
