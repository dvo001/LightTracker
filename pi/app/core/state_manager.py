import time
from typing import Dict, Any

from app.db.persistence import get_persistence


class StateManager:
    def __init__(self):
        self.p = get_persistence()

    def get_state(self) -> str:
        return self.p.get_setting("system.state", "SETUP")

    def set_state(self, state: str):
        self.p.upsert_setting("system.state", state)

    def readiness(self) -> Dict[str, Any]:
        # minimal readiness: mqtt_ok flag + anchors_online>=min + fixtures enabled
        mqtt_ok = str(self.p.get_setting("mqtt.ok", "false")).lower() == "true"
        anchors_online = self.p.anchors_online_count()
        min_anchors = int(self.p.get_setting("guards.min_anchors_online", 4) or 4)
        fixtures_enabled = any(f.get("enabled", 0) for f in self.p.list_fixtures())
        ready = mqtt_ok and anchors_online >= min_anchors and fixtures_enabled
        return {
            "ready": ready,
            "mqtt_ok": mqtt_ok,
            "anchors_online": anchors_online,
            "min_anchors": min_anchors,
            "fixtures_enabled": fixtures_enabled,
        }
