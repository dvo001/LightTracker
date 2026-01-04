#pragma once
#include <Arduino.h>
#include <vector>

// Shared protocol helpers for provisioning bridge/device.
static const uint16_t PB_MAGIC = 0x4250; // "PB"
static const uint8_t PB_VER = 0x01;
static const uint8_t PB_FLAG_ACK_REQ = 0x01;
static const uint8_t PB_FLAG_IS_FRAG = 0x02;
static const uint8_t PB_FLAG_LAST_FRAG = 0x04;
static const size_t PB_HDR_SIZE = 13;
static const size_t PB_MAX_PAYLOAD_PER_FRAME = 200;
static const size_t PB_MAX_TOTAL = 240;

enum PbMsgType : uint8_t {
  PB_PING = 0x01,
  PB_PING_ACK = 0x02,
  PB_WRITE_CFG = 0x10,
  PB_WRITE_ACK = 0x11,
  PB_READ_CFG = 0x12,
  PB_READ_ACK = 0x13,
  PB_APPLY = 0x14,
  PB_APPLY_ACK = 0x15,
  PB_REBOOT = 0x16,
  PB_REBOOT_ACK = 0x17,
  PB_NACK = 0x7E,
  PB_ERROR = 0x7F
};

struct PbHeader {
  uint16_t magic = PB_MAGIC;
  uint8_t ver = PB_VER;
  uint8_t msg_type = 0;
  uint8_t flags = 0;
  uint16_t seq = 0;
  uint8_t frag_idx = 0;
  uint8_t frag_cnt = 0;
  uint16_t payload_len = 0;
  uint16_t crc16 = 0;
};

uint16_t pb_crc16(const uint8_t* data, size_t len);
std::vector<uint8_t> pb_build_frame(const PbHeader& hdr, const uint8_t* payload, size_t len);
bool pb_parse_header(const uint8_t* data, size_t len, PbHeader& out);
