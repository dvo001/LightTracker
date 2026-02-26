#pragma once

#include <Arduino.h>

class BridgeDisplay {
public:
  void begin();
  void update(bool busy);

private:
  bool ready_ = false;
  uint32_t last_draw_ms_ = 0;
};
