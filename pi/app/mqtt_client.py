import json
import threading
import time
from typing import Optional, Callable

try:
    import paho.mqtt.client as mqtt
except Exception:
    mqtt = None

from app.db.persistence import get_persistence

class MQTTClientWrapper:
    def __init__(self, broker_host='localhost', broker_port=1883, tracking_engine=None, status_cb: Optional[Callable[[bool], None]] = None):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.tracking_engine = tracking_engine
        self._client = None
        self.connected = False
        self._status_cb = status_cb

    def _on_connect(self, client, userdata, flags, rc):
        try:
            client.subscribe('dev/+/status')
            client.subscribe('dev/+/ranges')
            client.subscribe('dev/+/cmd_ack')
            # mark mqtt ok
            try:
                p = get_persistence()
                p.upsert_setting('mqtt.ok', 'true')
            except Exception:
                pass
            self.connected = True
            if self._status_cb:
                try:
                    self._status_cb(True)
                except Exception:
                    pass
        except Exception:
            pass

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        if self._status_cb:
            try:
                self._status_cb(False)
            except Exception:
                pass
        try:
            p = get_persistence()
            p.upsert_setting('mqtt.ok', 'false')
        except Exception:
            pass

    def _on_message(self, client, userdata, msg):
        topic_parts = msg.topic.split('/')
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
        except Exception:
            return
        p = get_persistence()
        if len(topic_parts) >= 3 and topic_parts[0] == 'dev':
            mac = topic_parts[1]
            ttype = topic_parts[2]
            if ttype == 'status':
                ts_ms = int(payload.get('ts_ms', time.time()*1000))
                p.upsert_device({
                    'mac': mac,
                    'role': payload.get('role'),
                    'fw': payload.get('fw'),
                    'ip_last': payload.get('ip'),
                    'status': payload.get('status', 'ONLINE'),
                    'last_seen_at_ms': ts_ms
                })
            elif ttype == 'ranges':
                anchor_mac = payload.get('anchor_mac') or mac
                ts_ms = int(payload.get('ts_ms', time.time()*1000))
                ranges = payload.get('ranges', [])
                if anchor_mac and ranges and self.tracking_engine:
                    try:
                        self.tracking_engine.enqueue_range_batch(anchor_mac, ts_ms, ranges)
                    except Exception:
                        pass
            elif ttype == 'cmd_ack':
                # basic logging
                p.append_event('INFO', 'mqtt', 'cmd_ack', ref=mac, details_json=json.dumps(payload))

    def start(self):
        if mqtt is None:
            print('paho.mqtt not installed; mqtt client disabled')
            self.connected = False
            return
        self._client = mqtt.Client()
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect
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
        try:
            p = get_persistence()
            p.upsert_setting('mqtt.ok', 'false')
        except Exception:
            pass
