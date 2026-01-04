#pragma once
#include <Arduino.h>

typedef void (*EspNowRecvHandler)(const uint8_t *mac, const uint8_t *data, int len);

void espnow_init_bridge(EspNowRecvHandler h = nullptr);
bool espnow_send_frame(const uint8_t peer_mac[6], const uint8_t* data, size_t len);
bool espnow_add_peer(const uint8_t peer_mac[6]);
