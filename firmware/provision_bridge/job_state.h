#pragma once
#include <Arduino.h>
#include <array>

enum class JobStatus { IDLE, BUSY };

struct JobState {
  JobStatus status = JobStatus::IDLE;
  uint16_t seq_counter = 1;
  String current_id;
  std::array<uint8_t,6> current_mac{{0}};

  uint16_t next_seq(){ return seq_counter++; }
  void clear(){ status = JobStatus::IDLE; current_id = ""; current_mac = {0,0,0,0,0,0}; }
};
