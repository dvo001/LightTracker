#include <Arduino.h>
#include "common/device_identity.h"
#include "common/mqtt_client.h"
#include "common/json_payloads.h"

PiMqttClient mqtt;

unsigned long last_status = 0;

void setup() {
  Serial.begin(115200);
  delay(100);
  mqtt.begin("", "");
}

void loop() {
  mqtt.loop();
  unsigned long now = millis();
  if (now - last_status >= 5000) {
    String st = JsonPayloads::status_payload("ONLINE", "0.0.0.0", millis(), mqtt.reconnects, 0);
    String topic = String("dev/") + DeviceIdentity::mac_nocolon() + "/status";
    mqtt.publish(topic, st);
    last_status = now;
  }
  delay(10);
}
