#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "device_identity.h"
#include "mqtt_client.h"

// Simple display helper for 128x64 OLED (SSD1306 @ 0x3C, I2C on Makerfabs MaUWB ESP32-S3)

class LtDisplay {
public:
  Adafruit_SSD1306 oled;
  bool ready = false;
  unsigned long last_draw_ms = 0;
  int last_visible = -1;
  String last_alias = "";
  String last_mode = "";
  int last_rssi = -127;

  LtDisplay(): oled(128, 64, &Wire, -1) {}

  void begin() {
    Wire.begin(39, 38); // SDA=39, SCL=38 on MaUWB S3
    if (!oled.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
      ready = false;
      return;
    }
    ready = true;
    oled.clearDisplay();
    oled.display();
  }

  void draw(const String& alias, const String& mode, int visible_count, bool wifi_connected, int wifi_rssi, bool show_visible=true){
    if (!ready) return;
    last_draw_ms = millis();
    last_visible = visible_count;
    last_alias = alias;
    last_mode = mode;
    last_rssi = wifi_rssi;

    oled.clearDisplay();

    // MAC top-left
    oled.setTextSize(1);
    oled.setTextColor(SSD1306_WHITE);
    oled.setCursor(0, 0);
    oled.print(DeviceIdentity::mac_colon());

    // WiFi icon top-right (simple bars)
    draw_wifi_icon(wifi_connected, wifi_rssi);

    // Alias (large, left aligned without icon)
    oled.setTextSize(2);
    oled.setCursor(0, 18);
    String aname = alias.length() ? alias : String(mode);
    if (aname.length() > 12) {
      aname = aname.substring(0, 11) + "...";
    }
    oled.println(aname);

    // Bottom row: mode + visible count
    oled.setTextSize(1);
    oled.setCursor(0, 52);
    oled.print("Mode: ");
    draw_mode_icon(mode, 40, 50);

    if (show_visible){
      oled.setCursor(72, 52);
      oled.print(mode == "Tag" ? "Anchors: " : "Tags: ");
      oled.print(visible_count);
    }

    oled.display();
  }

private:
  void draw_wifi_icon(bool connected, int rssi){
    const int x = 112;
    const int y = 0;
    oled.drawRect(x, y, 15, 12, SSD1306_WHITE);
    if (!connected){
      oled.drawLine(x, y, x+14, y+11, SSD1306_WHITE);
      oled.drawLine(x, y+11, x+14, y, SSD1306_WHITE);
      return;
    }
    int bars = 3;
    if (rssi > -55) bars = 3;
    else if (rssi > -65) bars = 2;
    else if (rssi > -75) bars = 1;
    else bars = 0;
    for (int i=0;i<3;i++){
      if (i < bars){
        oled.fillRect(x+2 + i*4, y+10-(i*3), 3, 2+(i*3), SSD1306_WHITE);
      } else {
        oled.drawRect(x+2 + i*4, y+10-(i*3), 3, 2+(i*3), SSD1306_WHITE);
      }
    }
  }

  void draw_mode_icon(const String& mode, int x=0, int y=20){
    // Simple 12x12 icons
    const unsigned char tag_bits[] PROGMEM = {
      0b00000000, 0b0000,
      0b00111111, 0b1110,
      0b00100000, 0b0010,
      0b00100000, 0b0010,
      0b00100000, 0b0010,
      0b00101100, 0b1110,
      0b00101100, 0b1110,
      0b00100000, 0b0010,
      0b00100000, 0b0010,
      0b00100000, 0b0010,
      0b00111111, 0b1110,
      0b00000000, 0b0000,
      0b00000000, 0b0000,
    };
    const unsigned char anchor_bits[] PROGMEM = {
      0b00000110, 0b0000,
      0b00000110, 0b0000,
      0b00000110, 0b0000,
      0b00000110, 0b0000,
      0b01111111, 0b1110,
      0b01111111, 0b1110,
      0b00000110, 0b0000,
      0b00000110, 0b0000,
      0b00000110, 0b0000,
      0b00000110, 0b0000,
      0b00000110, 0b0000,
      0b00000000, 0b0000,
    };
    const unsigned char* bmp = (mode == "Tag") ? tag_bits : anchor_bits;
    oled.drawBitmap(x, y, bmp, 12, 12, SSD1306_WHITE);
  }
};
