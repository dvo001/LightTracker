#include "pb_proto.h"

uint16_t pb_crc16(const uint8_t* data, size_t len){
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < len; i++){
    crc ^= (uint16_t)data[i] << 8;
    for (int j = 0; j < 8; j++){
      if (crc & 0x8000) crc = (crc << 1) ^ 0x1021;
      else crc <<= 1;
    }
  }
  return crc;
}

std::vector<uint8_t> pb_build_frame(const PbHeader& hdr, const uint8_t* payload, size_t len){
  std::vector<uint8_t> out;
  out.reserve(PB_HDR_SIZE + len);
  auto push16 = [&](uint16_t v){ out.push_back(v & 0xFF); out.push_back((v >> 8) & 0xFF); };
  push16(hdr.magic);
  out.push_back(hdr.ver);
  out.push_back(hdr.msg_type);
  out.push_back(hdr.flags);
  push16(hdr.seq);
  out.push_back(hdr.frag_idx);
  out.push_back(hdr.frag_cnt);
  push16(hdr.payload_len);
  push16(0);
  out.insert(out.end(), payload, payload + len);
  uint16_t crc = pb_crc16(out.data(), out.size());
  out[11] = crc & 0xFF;
  out[12] = (crc >> 8) & 0xFF;
  return out;
}

bool pb_parse_header(const uint8_t* data, size_t len, PbHeader& out){
  if (len < PB_HDR_SIZE) return false;
  out.magic = data[0] | (data[1] << 8);
  out.ver = data[2];
  out.msg_type = data[3];
  out.flags = data[4];
  out.seq = data[5] | (data[6] << 8);
  out.frag_idx = data[7];
  out.frag_cnt = data[8];
  out.payload_len = data[9] | (data[10] << 8);
  out.crc16 = data[11] | (data[12] << 8);
  if (out.magic != PB_MAGIC || out.ver != PB_VER) return false;
  uint16_t crc = pb_crc16(data, PB_HDR_SIZE - 2 + out.payload_len);
  if (crc != out.crc16) return false;
  return true;
}
