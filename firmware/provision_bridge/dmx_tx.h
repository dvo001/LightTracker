#pragma once

#include <Arduino.h>
#include <stdint.h>

// Sends a DMX frame (513 bytes including start code).
// Returns true on success, false on failure. If false, dmx_tx_last_error() explains why.
bool dmx_tx_send_frame(const uint8_t* frame, size_t len);

// Last error string for diagnostics.
const char* dmx_tx_last_error();

// Expose pins used by the DMX UART for status/debug.
int dmx_tx_pin();
int dmx_rx_pin();
