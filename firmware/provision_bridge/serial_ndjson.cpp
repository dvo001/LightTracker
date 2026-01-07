#include "serial_ndjson.h"
#include <Arduino.h>

void SerialNdjson::loop(){
  if (!stream) return;
  while (stream->available()){
    int c = stream->read();
    if (c < 0) break;
    if (c == 0) continue; // skip spurious NUL
    if (c == '\r') continue; // ignore CR, use LF as delimiter
    if (c == '\n'){
      String line = buf;
      line.trim();
      if (line.length() > 0){
        Serial.printf("bridge: got line len=%u\n", (unsigned)line.length());
        if (line.length() > 4096){
          Serial.println("bridge: serial line too long, dropping");
          send_line("{\"v\":1,\"status\":\"error\",\"err\":{\"code\":\"SERIAL_OVERFLOW\"}}");
        }else{
          DynamicJsonDocument doc(1536);
          DeserializationError err = deserializeJson(doc, line);
          if (!err && handler){
            handler(doc);
          }else if (err){
            // attempt recovery: strip leading noise up to first '{'
            int brace = line.indexOf('{');
            if (brace > 0){
              String sub = line.substring(brace);
              DeserializationError err2 = deserializeJson(doc, sub);
              if (!err2 && handler){
                Serial.printf("bridge: recovered after stripping %d bytes of noise\n", brace);
                handler(doc);
                buf = "";
                continue;
              }
            }
            Serial.printf("bridge: serial parse error: %s line='%s'\n", err.c_str(), line.c_str());
            // dump first few bytes in hex to spot hidden chars
            Serial.print("bridge: line hex=");
            size_t dump = min((size_t)16, (size_t)line.length());
            for (size_t i=0;i<dump;i++){
              Serial.printf("%02X ", (uint8_t)line[i]);
            }
            Serial.println();
          }
        }
      } else {
        Serial.println("bridge: empty line");
      }
      buf = "";
      continue;
    }
    if (buf.length() < 4096) buf += (char)c;
  }
}

void SerialNdjson::send_line(const String& line){
  if (!stream) return;
  stream->println(line);
}
