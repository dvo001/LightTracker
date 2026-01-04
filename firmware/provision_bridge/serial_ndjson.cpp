#include "serial_ndjson.h"

void SerialNdjson::loop(){
  if (!stream) return;
  while (stream->available()){
    int c = stream->read();
    if (c < 0) break;
    if (c == '\n'){
      if (buf.length() > 0){
        if (buf.length() > 4096){
          send_line("{\"v\":1,\"status\":\"error\",\"err\":{\"code\":\"SERIAL_OVERFLOW\"}}");
        }else{
          DynamicJsonDocument doc(1024);
          DeserializationError err = deserializeJson(doc, buf);
          if (!err && handler){
            handler(doc);
          }
        }
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
