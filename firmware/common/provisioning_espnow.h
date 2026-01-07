#pragma once
#include <Arduino.h>

// Device-side provisioning (ESP-NOW RX/TX) skeleton per CODEX task.
void prov_init();
void prov_loop();
bool prov_is_active();
