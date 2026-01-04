"""
Reference server-side client (pyserial) skeleton for ESP-NOW provisioning bridge.
Implements NDJSON request/response framing with correlation id.
"""
import json, time, uuid, threading
import serial

class ProvisionBridgeClient:
    def __init__(self, port, baud=115200, timeout=1.0):
        self.ser = serial.Serial(port, baudrate=baud, timeout=timeout)
        self.lock = threading.Lock()

    def _send(self, obj):
        line = json.dumps(obj) + "\n"
        self.ser.write(line.encode("utf-8"))

    def _recv(self, req_id, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.ser.readline()
            if not line:
                continue
            try:
                msg = json.loads(line.decode("utf-8"))
            except Exception:
                continue
            if msg.get("id") == req_id:
                return msg
        return None

    def call(self, op, payload, timeout=5.0):
        req_id = payload.get("id") or str(uuid.uuid4())
        payload["id"] = req_id
        payload["v"] = payload.get("v", 1)
        with self.lock:
            self._send(payload)
            return self._recv(req_id, timeout)

    def hello(self):
        return self.call("hello", {"op":"hello","client":"provision_server","cap":["provision","readback","reboot"]}, timeout=2.0)

# Example usage:
# client = ProvisionBridgeClient("/dev/ttyUSB0")
# print(client.hello())
