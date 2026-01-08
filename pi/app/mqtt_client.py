import hashlib
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
        self._loop_thread = None

    def _ensure_anchor_index(self, mac: str, p) -> Optional[int]:
        try:
            current = p.get_device_setting(mac, "anchor_index", "")
            if current != "":
                idx = int(current)
                if 0 <= idx <= 7:
                    return idx
        except Exception:
            pass

        used = set()
        try:
            rows = p.list_device_settings_by_key("anchor_index")
            for r in rows:
                try:
                    used.add(int(r.get("value")))
                except Exception:
                    pass
        except Exception:
            pass

        for i in range(8):
            if i not in used:
                try:
                    p.upsert_device_setting(mac, "anchor_index", str(i))
                except Exception:
                    pass
                return i
        return None

    def _build_default_cfg(self, mac: str, p):
        cfg = {}
        ssid = (p.get_setting('wifi.ssid', '') or '').strip()
        wpass = p.get_setting('wifi.pass', '') or ''
        host = (p.get_setting('mqtt.host', '') or '').strip()
        port_raw = p.get_setting('mqtt.port', '') or ''
        if not host:
            host = self.broker_host
        try:
            port = int(port_raw) if port_raw else int(self.broker_port)
        except Exception:
            port = int(self.broker_port)
        if ssid:
            cfg['ssid'] = ssid
            cfg['pass'] = wpass
        if host:
            cfg['mqtt_host'] = host
        if port:
            cfg['mqtt_port'] = port
        dev = p.get_device(mac)
        if dev and dev.get('alias'):
            cfg['alias'] = dev['alias']
        if dev and (dev.get('role') or '').upper() == 'ANCHOR':
            idx = self._ensure_anchor_index(mac, p)
            if idx is not None:
                cfg['anchor_index'] = idx
        return cfg

    def _cfg_hash(self, cfg: dict) -> str:
        payload = json.dumps(cfg, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _maybe_apply_defaults(self, mac: str, p) -> bool:
        if not self._client:
            return False
        cfg = self._build_default_cfg(mac, p)
        if not cfg:
            return False
        cfg_hash = self._cfg_hash(cfg)
        last_hash = p.get_device_setting(mac, "cfg_hash", "")
        if last_hash == cfg_hash:
            return False
        payload = {
            "type": "cmd",
            "cmd": "apply_settings",
            "cmd_id": f"auto_cfg_{int(time.time()*1000)}",
            "settings": cfg,
        }
        topic = f"dev/{mac}/cmd"
        self._client.publish(topic, json.dumps(payload), qos=1)
        p.upsert_device_setting(mac, "cfg_hash", cfg_hash)
        p.upsert_device_setting(mac, "cfg_last_sent_ms", str(int(time.time()*1000)))
        try:
            p.append_event('INFO', 'mqtt', 'auto_apply_settings', ref=mac, details_json=json.dumps(cfg))
        except Exception:
            pass
        return True

    def apply_defaults_all(self) -> int:
        if not self._client:
            return 0
        p = get_persistence()
        count = 0
        for dev in p.list_devices():
            mac = dev.get("mac")
            if not mac:
                continue
            try:
                if self._maybe_apply_defaults(mac, p):
                    count += 1
            except Exception:
                pass
        return count

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
        now_ms = int(time.time()*1000)
        def _coerce_ts_ms(ts_ms: Optional[object]) -> int:
            try:
                t = int(ts_ms)
            except Exception:
                return now_ms
            # treat non-epoch (device uptime) as invalid
            if t < 1_000_000_000_000:
                return now_ms
            return t
        if len(topic_parts) >= 3 and topic_parts[0] == 'dev':
            mac = topic_parts[1]
            ttype = topic_parts[2]
            if ttype == 'status':
                ts_ms = _coerce_ts_ms(payload.get('ts_ms', now_ms))
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
                ts_ms = _coerce_ts_ms(payload.get('ts_ms', now_ms))
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
            self._loop_thread = t
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
        self.connected = False
        self._client = None
        self._loop_thread = None

    def restart(self, broker_host: Optional[str] = None, broker_port: Optional[int] = None) -> bool:
        if broker_host:
            self.broker_host = broker_host
        if broker_port:
            self.broker_port = broker_port
        self.stop()
        self.start()
        return self.connected
