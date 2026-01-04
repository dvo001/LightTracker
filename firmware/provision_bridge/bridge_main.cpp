#include <Arduino.h>
#include "serial_ndjson.h"
#include "../common/pb_proto.h"
#include "espnow_link.h"
#include "job_state.h"
#include "../common/cbor_codec.h"
#include "bridge_ops.h"
#include <esp_task_wdt.h>
#include <esp_system.h>

// Firmware skeleton for ESP-NOW provisioning bridge (Channel 6, unencrypted).
// This is only a stub; command handlers must be implemented per CODEX_TASK_FILE_ESP-NOW_Provisioning_Bridge_v1.

SerialNdjson g_serial;
JobState g_job;

void setup(){
  disableCore0WDT();
  disableCore1WDT();
  esp_task_wdt_deinit();
  Serial.begin(115200);
  delay(50);
  Serial.printf("bridge: booting, reset_reason=%d\n", esp_reset_reason());
  g_serial.begin(&Serial, [](const DynamicJsonDocument& doc){
    String resp = bridge_handle_msg(doc);
    if (resp.length()) g_serial.send_line(resp);
  });
  Serial.println(F("bridge: serial ready"));
  espnow_init_bridge();
  Serial.println(F("bridge: espnow init done"));
}

void loop(){
  // TODO: parse NDJSON, dispatch ops, manage retries/acks.
  g_serial.loop();
  delay(10);
}
