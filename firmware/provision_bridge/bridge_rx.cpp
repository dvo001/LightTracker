#include "bridge_rx.h"
#include "espnow_link.h"
#include <Arduino.h>

static volatile bool g_has = false;
static RxState g_rx;
static struct FragBuf {
  bool active = false;
  uint8_t src[6];
  uint16_t seq = 0;
  uint8_t msg_type = 0;
  uint8_t frag_cnt = 0;
  uint32_t last_ms = 0;
  std::vector<std::vector<uint8_t>> frags;
} g_frag;

static void _handler(const uint8_t *mac, const uint8_t *data, int len){
  PbHeader hdr;
  if (!pb_parse_header(data, len, hdr)) return;
  const uint8_t* payload = data + PB_HDR_SIZE;
  size_t paylen = len - PB_HDR_SIZE;

  if (hdr.flags & PB_FLAG_IS_FRAG){
    // init buffer
    if (!g_frag.active || memcmp(g_frag.src, mac,6)!=0 || g_frag.seq!=hdr.seq || g_frag.msg_type!=hdr.msg_type){
      g_frag.active = true;
      memcpy(g_frag.src, mac,6);
      g_frag.seq = hdr.seq;
      g_frag.msg_type = hdr.msg_type;
      g_frag.frag_cnt = hdr.frag_cnt;
      g_frag.frags.clear();
      g_frag.frags.resize(hdr.frag_cnt);
    }
    if (hdr.frag_idx < g_frag.frags.size()){
      g_frag.frags[hdr.frag_idx].assign(payload, payload+paylen);
      g_frag.last_ms = millis();
    }
    bool complete = true;
    for (uint8_t i=0;i<g_frag.frag_cnt;i++){
      if (g_frag.frags[i].empty()) { complete=false; break; }
    }
    if (complete){
      // concat
      std::vector<uint8_t> full;
      for (auto& f : g_frag.frags) full.insert(full.end(), f.begin(), f.end());
      g_rx.has_msg = true;
      memcpy((void*)g_rx.src_mac, mac, 6);
      g_rx.hdr = hdr;
      g_rx.payload = full;
      g_has = true;
      g_frag.active = false;
    }
  }else{
    g_rx.has_msg = true;
    memcpy((void*)g_rx.src_mac, mac, 6);
    g_rx.hdr = hdr;
    g_rx.payload.assign(payload, payload + paylen);
    g_has = true;
  }
}

void bridge_rx_reset(){
  g_has = false;
  g_rx = RxState{};
  g_frag.active = false;
}

bool bridge_rx_wait(uint16_t expect_seq, uint8_t expect_type, const uint8_t* mac, uint32_t timeout_ms, RxState& out){
  uint32_t start = millis();
  while (millis() - start < timeout_ms){
    if (g_frag.active && millis() - g_frag.last_ms > 1200){
      g_frag.active = false;
    }
    if (g_has){
      noInterrupts();
      bool match = g_rx.has_msg &&
                   g_rx.hdr.seq == expect_seq &&
                   g_rx.hdr.msg_type == expect_type &&
                   memcmp(g_rx.src_mac, mac, 6) == 0;
      if (match){
        out = g_rx;
        g_has = false;
        interrupts();
        return true;
      }
      g_has = false;
      interrupts();
    }
    delay(5);
  }
  return false;
}

struct RxInit { RxInit(){ espnow_init_bridge(_handler); } };
static RxInit _rx_init;
