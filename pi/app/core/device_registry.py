from typing import Dict


class DeviceRegistry:
    def __init__(self):
        self._devices: Dict[str, dict] = {}

    def upsert(self, mac: str, info: dict):
        self._devices[mac] = {**self._devices.get(mac, {}), **info}

    def get(self, mac: str):
        return self._devices.get(mac)

    def list(self):
        return list(self._devices.values())
# Device registry
