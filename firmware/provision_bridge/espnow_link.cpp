#include "espnow_link.h"
#include <esp_wifi.h>
#include <esp_now.h>
#include <WiFi.h>
#include <esp_err.h>

static EspNowRecvHandler g_handler = nullptr;
static void _on_recv(const uint8_t *mac, const uint8_t *incomingData, int len){
  if (g_handler) g_handler(mac, incomingData, len);
}

void espnow_init_bridge(EspNowRecvHandler h){
  g_handler = h;
  WiFi.mode(WIFI_STA);
  esp_wifi_set_channel(6, WIFI_SECOND_CHAN_NONE);
  if (esp_now_init() != ESP_OK){
    Serial.println("esp_now_init failed");
    return;
  }
  esp_now_register_recv_cb(_on_recv);
}

bool espnow_send_frame(const uint8_t peer_mac[6], const uint8_t* data, size_t len){
  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, peer_mac, 6);
  peer.channel = 6;
  peer.encrypt = false;
  esp_now_del_peer(peer.peer_addr);
  esp_err_t add = esp_now_add_peer(&peer);
  if (add != ESP_OK){
    Serial.printf("bridge: espnow add_peer failed err=%d\n", add);
    return false;
  }
  esp_err_t err = esp_now_send(peer.peer_addr, data, len);
  if (err != ESP_OK){
    Serial.printf("bridge: espnow send failed err=%d len=%u to %02X:%02X:%02X:%02X:%02X:%02X\n",
                  err, (unsigned)len,
                  peer_mac[0], peer_mac[1], peer_mac[2], peer_mac[3], peer_mac[4], peer_mac[5]);
    return false;
  }
  Serial.printf("bridge: espnow send ok len=%u to %02X:%02X:%02X:%02X:%02X:%02X\n",
                (unsigned)len,
                peer_mac[0], peer_mac[1], peer_mac[2], peer_mac[3], peer_mac[4], peer_mac[5]);
  return true;
}

bool espnow_add_peer(const uint8_t peer_mac[6]){
  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, peer_mac, 6);
  peer.channel = 6;
  peer.encrypt = false;
  esp_now_del_peer(peer.peer_addr);
  return esp_now_add_peer(&peer) == ESP_OK;
}
