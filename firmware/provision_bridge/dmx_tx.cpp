#include "dmx_tx.h"

#include <driver/uart.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

namespace {

#ifndef BRIDGE_DMX_UART_NUM
#define BRIDGE_DMX_UART_NUM UART_NUM_1
#endif

#ifndef BRIDGE_DMX_TX_PIN
#define BRIDGE_DMX_TX_PIN 17
#endif

#ifndef BRIDGE_DMX_RX_PIN
#define BRIDGE_DMX_RX_PIN 18
#endif

#ifndef BRIDGE_DMX_BREAK_BITS
#define BRIDGE_DMX_BREAK_BITS 26
#endif

#ifndef BRIDGE_DMX_MAB_US
#define BRIDGE_DMX_MAB_US 12
#endif

#ifndef BRIDGE_DMX_TX_TIMEOUT_MS
#define BRIDGE_DMX_TX_TIMEOUT_MS 40
#endif

bool g_initialized = false;
String g_last_error;

bool fail(const char* msg) {
  g_last_error = msg ? msg : "unknown";
  return false;
}

bool ensure_init() {
  if (g_initialized) return true;

  uart_config_t cfg = {};
  cfg.baud_rate = 250000;
  cfg.data_bits = UART_DATA_8_BITS;
  cfg.parity = UART_PARITY_DISABLE;
  cfg.stop_bits = UART_STOP_BITS_2;
  cfg.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
  cfg.rx_flow_ctrl_thresh = 0;

  esp_err_t err = uart_param_config(BRIDGE_DMX_UART_NUM, &cfg);
  if (err != ESP_OK) return fail("uart_param_config failed");

  err = uart_set_pin(
      BRIDGE_DMX_UART_NUM,
      BRIDGE_DMX_TX_PIN,
      BRIDGE_DMX_RX_PIN,
      UART_PIN_NO_CHANGE,
      UART_PIN_NO_CHANGE
  );
  if (err != ESP_OK) return fail("uart_set_pin failed");

  if (!uart_is_driver_installed(BRIDGE_DMX_UART_NUM)) {
    // Some ESP-IDF versions reject 0-sized buffers. Keep a small RX buffer
    // even though we only transmit DMX.
    err = uart_driver_install(BRIDGE_DMX_UART_NUM, 256, 0, 0, nullptr, 0);
    if (err != ESP_OK) return fail("uart_driver_install failed");
  }

  g_initialized = true;
  g_last_error = "";
  return true;
}

}  // namespace

bool dmx_tx_send_frame(const uint8_t* frame, size_t len) {
  if (!frame) return fail("null frame");
  if (len != 513) return fail("frame must be 513 bytes");
  if (!ensure_init()) return false;

  // Ensure previous transfer is fully done before generating break.
  uart_wait_tx_done(BRIDGE_DMX_UART_NUM, pdMS_TO_TICKS(BRIDGE_DMX_TX_TIMEOUT_MS));

  // Generate DMX break by inverting TX idle level for a short period.
  // This is more portable across ESP-IDF variants than write_bytes_with_break(0 bytes).
  esp_err_t err = uart_set_line_inverse(BRIDGE_DMX_UART_NUM, UART_SIGNAL_TXD_INV);
  if (err != ESP_OK) return fail("uart break invert failed");
  delayMicroseconds(110);
  err = uart_set_line_inverse(BRIDGE_DMX_UART_NUM, UART_SIGNAL_INV_DISABLE);
  if (err != ESP_OK) return fail("uart break release failed");
  delayMicroseconds(BRIDGE_DMX_MAB_US);

  int written = uart_write_bytes(BRIDGE_DMX_UART_NUM, reinterpret_cast<const char*>(frame), len);
  if (written != (int)len) return fail("uart frame write failed");

  uart_wait_tx_done(BRIDGE_DMX_UART_NUM, pdMS_TO_TICKS(BRIDGE_DMX_TX_TIMEOUT_MS));
  g_last_error = "";
  return true;
}

const char* dmx_tx_last_error() {
  return g_last_error.c_str();
}

int dmx_tx_pin() {
  return BRIDGE_DMX_TX_PIN;
}

int dmx_rx_pin() {
  return BRIDGE_DMX_RX_PIN;
}
