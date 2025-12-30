import threading
import time
import logging
import json
from typing import Optional

import paho.mqtt.client as mqtt

from app.mqtt import topics, payloads
from app.db.persistence import Persistence

logger = logging.getLogger("pi.mqtt")


class MQTTManager:
    def __init__(self, persistence: Persistence, host: str = None, port: int = None):
        self.persistence = persistence
        self.host = host
        self.port = port
        self._stop = threading.Event()
        self.client: Optional[mqtt.Client] = None

    def run(self):
        host = self.host or __import__('app').config.MQTT_HOST
        port = self.port or __import__('app').config.MQTT_PORT
        client = mqtt.Client()

        def on_connect(c, userdata, flags, rc):
            logger.info("MQTT connected: rc=%s", rc)
            # subscribe
            c.subscribe(topics.STATUS_TOPIC)
            c.subscribe(topics.CMD_ACK_TOPIC)
            c.subscribe(topics.RANGES_TOPIC)

        def on_message(c, userdata, msg):
            t = msg.topic
            payload = payloads.parse_json_payload(msg.payload)
            try:
                # infer mac from topic
                parts = t.split('/')
                mac = parts[1] if len(parts) > 1 else None
                if t.startswith('dev/') and t.endswith('/status'):
                    role = payload.get('role') if payload else None
                    self.persistence.upsert_device(mac=mac, role=role, fw=(payload.get('fw') if payload else None), ip=(payload.get('ip') if payload else None), status=(payload.get('status') if payload else None), ts_ms=(payload.get('ts_ms') if payload and 'ts_ms' in payload else None))
                else:
                    # generic log
                    self.persistence.insert_event('INFO', 'mqtt', 'message', mac or '', json.dumps({'topic': t, 'payload': payload}))
            except Exception as e:
                logger.exception("Error handling MQTT message")
                try:
                    self.persistence.insert_event('ERROR', 'mqtt', 'parse_error', mac or '', json.dumps({'topic': t, 'error': str(e)}))
                except Exception:
                    pass

        client.on_connect = on_connect
        client.on_message = on_message

        self.client = client

        while not self._stop.is_set():
            try:
                client.connect(host, port, keepalive=60)
                client.loop_start()
                # run until stopped
                while not self._stop.wait(1):
                    time.sleep(0.1)
                client.loop_stop()
                client.disconnect()
            except Exception:
                logger.exception("MQTT connection failed, retrying in 5s")
                time.sleep(5)

    def stop(self):
        self._stop.set()
        try:
            if self.client:
                self.client.disconnect()
        except Exception:
            pass
# MQTT manager
