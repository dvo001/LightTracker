#pragma once
#include <Arduino.h>

#ifndef LT_BATTERY_PIN
#define LT_BATTERY_PIN 4
#endif
#ifndef LT_BATTERY_VREF
#define LT_BATTERY_VREF 3.3f
#endif
#ifndef LT_BATTERY_DIVIDER
#define LT_BATTERY_DIVIDER 2.0f
#endif

inline void battery_init() {
#if LT_BATTERY_PIN >= 0
  pinMode(LT_BATTERY_PIN, INPUT);
  analogReadResolution(12);
#endif
}

inline float battery_read_voltage() {
#if LT_BATTERY_PIN < 0
  return -1.0f;
#else
  int raw = analogRead(LT_BATTERY_PIN);
  if (raw < 0) return -1.0f;
  return LT_BATTERY_VREF * (float)raw / 4096.0f * LT_BATTERY_DIVIDER;
#endif
}
