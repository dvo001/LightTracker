#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include "job_state.h"

// Stubbed job executor: validate request, set BUSY, return immediate UNSUPPORTED until ESP-NOW side is finished.

String handle_provision_write(const DynamicJsonDocument& doc, JobState& job);
String handle_provision_read(const DynamicJsonDocument& doc, JobState& job);
String handle_reboot(const DynamicJsonDocument& doc, JobState& job);
String handle_ping(const DynamicJsonDocument& doc, JobState& job);
