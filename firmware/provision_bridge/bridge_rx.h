#pragma once
#include <Arduino.h>
#include "../common/pb_proto.h"

struct RxState {
  bool has_msg = false;
  uint8_t src_mac[6];
  PbHeader hdr;
  std::vector<uint8_t> payload;
};

void bridge_rx_reset();
bool bridge_rx_wait(uint16_t expect_seq, uint8_t expect_type, const uint8_t* mac, uint32_t timeout_ms, RxState& out);
