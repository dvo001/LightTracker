#include <Arduino.h>
#include "common/device_identity.h"
#include "common/mqtt_client.h"
#include "common/json_payloads.h"
#include "common/cmd_handler.h"
#include "common/display.h"
#include "common/provisioning_espnow.h"

PiMqttClient mqtt;
CmdHandler cmdh;
LtDisplay ldisplay;

unsigned long last_status = 0;

void setup() {
  Serial.begin(115200);
  delay(100);
  mqtt.load_config_from_nvs();
  mqtt.begin();
  mqtt.on_cmd = [](const String& topic, const String& payload){
    cmdh.handle(payload.c_str(), mqtt);
  };
  ldisplay.begin();
  prov_init();
}

void loop() {
  prov_loop();
  mqtt.loop();
  unsigned long now = millis();
  if (now - last_status >= 5000) {
    String st = JsonPayloads::status_payload("ONLINE", "0.0.0.0", millis(), mqtt.reconnects, 0);
    String topic = String("dev/") + DeviceIdentity::mac_nocolon() + "/status";
    mqtt.publish(topic, st);
    last_status = now;
  }
  delay(10);

  // display update (every ~1s)
  static unsigned long last_disp = 0;
  if (millis() - last_disp > 1000){
    int rssi = (WiFi.status() == WL_CONNECTED) ? WiFi.RSSI() : -127;
    String alias = mqtt.device_alias.length() ? mqtt.device_alias : String("Tag");
    // Tag: keine lokale Info über sichtbare Anchors, daher ohne Counter anzeigen
    ldisplay.draw(alias, "Tag", 0, WiFi.status() == WL_CONNECTED, rssi, false);
    last_disp = millis();
  }
}
