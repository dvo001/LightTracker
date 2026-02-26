#include <Arduino.h>
#include "serial_ndjson.h"
#include "../common/pb_proto.h"
#include "espnow_link.h"
#include "job_state.h"
#include "../common/cbor_codec.h"
#include "bridge_ops.h"
#include "bridge_rx.h"
#include "espnow_link.h"
#include "bridge_display.h"
#include "bridge_status.h"
#include <esp_system.h>
#include <esp_wifi.h>

#ifndef BRIDGE_SERIAL_BAUD
#define BRIDGE_SERIAL_BAUD 115200
#endif

SerialNdjson g_serial;
JobState g_job;
BridgeDisplay g_display;

void setup(){
  bridge_status_reset();
  Serial.begin(BRIDGE_SERIAL_BAUD);
  delay(50);
  Serial.printf(
      "bridge: booting, reset_reason=%d serial_baud=%d\n",
      esp_reset_reason(),
      BRIDGE_SERIAL_BAUD
  );
  g_serial.begin(&Serial, [](const DynamicJsonDocument& doc){
    const char* op = doc["op"] | "";
    const char* id = doc["id"] | "";
    Serial.printf("bridge: serial rx op=%s id=%s\n", op, id);
    String resp = bridge_handle_msg(doc);
    if (resp.length()) g_serial.send_line(resp);
  });
  Serial.println(F("bridge: serial ready"));
#if defined(BRIDGE_ENABLE_ESPNOW)
  bridge_rx_init();
  bridge_status_mark_espnow(espnow_is_ready());
  uint8_t primary = 0; wifi_second_chan_t second = WIFI_SECOND_CHAN_NONE;
  esp_wifi_get_channel(&primary, &second);
  Serial.printf("bridge: espnow init done ch=%u sec=%u\n", primary, (unsigned)second);
#endif
  g_display.begin();
}

void loop(){
  // TODO: parse NDJSON, dispatch ops, manage retries/acks.
  g_serial.loop();
  static uint32_t next_alive_log_ms = 0;
  uint32_t now = millis();
  if (now >= next_alive_log_ms) {
    Serial.printf("bridge: alive %lu\n", (unsigned long)now);
    extern JobState g_job;
    Serial.printf("bridge: seq_counter=%u status=%s\n", g_job.seq_counter, g_job.status == JobStatus::BUSY ? "BUSY" : "IDLE");
    next_alive_log_ms = now + 5000;
  }
  g_display.update(g_job.status == JobStatus::BUSY);
  delay(10);
}
