#include "bridge_display.h"

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#include "bridge_status.h"

#ifndef BRIDGE_OLED_ENABLE
#define BRIDGE_OLED_ENABLE 1
#endif

#ifndef BRIDGE_OLED_SDA_PIN
#define BRIDGE_OLED_SDA_PIN 39
#endif

#ifndef BRIDGE_OLED_SCL_PIN
#define BRIDGE_OLED_SCL_PIN 38
#endif

#ifndef BRIDGE_OLED_I2C_ADDR
#define BRIDGE_OLED_I2C_ADDR 0x3C
#endif

#ifndef BRIDGE_OLED_REFRESH_MS
#define BRIDGE_OLED_REFRESH_MS 250
#endif

namespace {
Adafruit_SSD1306 g_oled(128, 64, &Wire, -1);

String fmt_dmx(const BridgeStatusSnapshot& st) {
  if (!st.dmx_seen) return "DMX:--";
  return String("DMX:") + (st.dmx_ok ? "OK" : "ERR");
}

String fmt_esp(const BridgeStatusSnapshot& st) {
  if (!st.espnow_seen) return "ESP:--";
  return String("ESP:") + (st.espnow_ok ? "OK" : "ERR");
}
}  // namespace

void BridgeDisplay::begin() {
#if BRIDGE_OLED_ENABLE
  Wire.begin(BRIDGE_OLED_SDA_PIN, BRIDGE_OLED_SCL_PIN);
  ready_ = g_oled.begin(SSD1306_SWITCHCAPVCC, BRIDGE_OLED_I2C_ADDR);
  if (ready_) {
    g_oled.clearDisplay();
    g_oled.display();
  }
#else
  ready_ = false;
#endif
}

void BridgeDisplay::update(bool busy) {
  if (!ready_) return;
  uint32_t now = millis();
  if (now - last_draw_ms_ < BRIDGE_OLED_REFRESH_MS) return;
  last_draw_ms_ = now;

  BridgeStatusSnapshot st = bridge_status_snapshot();

  g_oled.clearDisplay();
  g_oled.setTextSize(1);
  g_oled.setTextColor(SSD1306_WHITE);

  // Top line is the yellow area on dual-color 0.96" OLED modules.
  g_oled.setCursor(0, 0);
  g_oled.print(fmt_dmx(st));
  g_oled.print(" ");
  g_oled.print(fmt_esp(st));

  g_oled.setCursor(0, 18);
  g_oled.print("Bridge ");
  g_oled.print(busy ? "BUSY" : "IDLE");

  g_oled.setCursor(0, 30);
  g_oled.print("I2C ");
  g_oled.print(BRIDGE_OLED_SDA_PIN);
  g_oled.print("/");
  g_oled.print(BRIDGE_OLED_SCL_PIN);
  g_oled.print(" A:0x");
  g_oled.print(BRIDGE_OLED_I2C_ADDR, HEX);

  if (st.dmx_seen) {
    g_oled.setCursor(0, 42);
    g_oled.print("DMX age ");
    g_oled.print((now - st.dmx_last_ms) / 1000);
    g_oled.print("s");
  }
  if (st.espnow_seen) {
    g_oled.setCursor(0, 54);
    g_oled.print("ESP age ");
    g_oled.print((now - st.espnow_last_ms) / 1000);
    g_oled.print("s");
  }

  g_oled.display();
}
