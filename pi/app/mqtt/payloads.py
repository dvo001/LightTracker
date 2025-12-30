import json


def parse_json_payload(payload_bytes: bytes):
    try:
        return json.loads(payload_bytes.decode('utf-8'))
    except Exception:
        return None
# MQTT payload schemas
