import json
import threading
import time
from typing import Optional

try:
    import paho.mqtt.client as mqtt
except Exception:
    mqtt = None

class MQTTClientWrapper:
    def __init__(self, broker_host='localhost', broker_port=1883, tracking_engine=None):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.tracking_engine = tracking_engine
        self._client = None
        self.connected = False

    def _on_connect(self, client, userdata, flags, rc):
        try:
            client.subscribe('lighttracking/anchors/+/range_batch')
        except Exception:
            pass

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
        except Exception:
            return
        anchor_mac = payload.get('anchor_mac')
        ts_ms = int(payload.get('ts_ms', time.time()*1000))
        ranges = payload.get('ranges', [])
        if not anchor_mac or not ranges:
            return
        if self.tracking_engine:
            try:
                self.tracking_engine.enqueue_range_batch(anchor_mac, ts_ms, ranges)
            except Exception:
                pass

    def start(self):
        if mqtt is None:
            print('paho.mqtt not installed; mqtt client disabled')
            self.connected = False
            return
        self._client = mqtt.Client()
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        try:
            self._client.connect(self.broker_host, self.broker_port, 60)
            t = threading.Thread(target=self._client.loop_forever, daemon=True)
            t.start()
            self.connected = True
        except Exception as e:
            print('mqtt connect failed', e)
            self.connected = False

    def stop(self):
        try:
            if self._client:
                self._client.disconnect()
        except Exception:
            pass
