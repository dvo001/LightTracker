#pragma once
#include <Arduino.h>

namespace DeviceIdentity {

inline String mac_colon() {
  uint8_t mac[6];
  esp_read_mac(mac, ESP_MAC_WIFI_STA);
  char buf[18];
  sprintf(buf, "%02X:%02X:%02X:%02X:%02X:%02X", mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);
  return String(buf);
}

inline String mac_nocolon() {
  String s = mac_colon();
  s.replace(":", "");
  return s;
}

inline String role() {
#ifdef ROLE_ANCHOR
  return String("ANCHOR");
#elif defined(ROLE_TAG)
  return String("TAG");
#else
  return String("UNKNOWN");
#endif
}

inline const char* fw_version() { return "0.1.0"; }

}
// MAC, role, fw
