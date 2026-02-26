import base64
import json
import threading
import time
import uuid

try:
    import serial
except Exception:
    serial = None


class BridgeUartDmxDriver:
    """
    DMX output driver via the provisioning bridge serial protocol.

    Sends NDJSON `dmx_write` commands to an ESP bridge over USB/UART.
    The bridge firmware then outputs DMX on ESP GPIO pins.
    """

    def __init__(self, port: str = "/dev/ttyUSB0", baud: int = 115200, ack_timeout_s: float = 0.6):
        self.port = port
        self.baud = int(baud)
        self.ack_timeout_s = float(ack_timeout_s)
        self.ser = None
        self._lock = threading.Lock()

    def close(self):
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    def _ensure_open(self):
        if self.ser is not None:
            return
        if serial is None:
            raise RuntimeError("pyserial not installed")
        self.ser = serial.Serial(
            self.port,
            baudrate=self.baud,
            timeout=0.02,
            write_timeout=0.2,
            rtscts=False,
            dsrdtr=False,
        )
        try:
            self.ser.dtr = False
            self.ser.rts = False
        except Exception:
            pass
        try:
            self.ser.reset_input_buffer()
        except Exception:
            pass

    def _wait_ack(self, req_id: str):
        deadline = time.time() + self.ack_timeout_s
        while time.time() < deadline:
            raw = self.ser.readline()
            if not raw:
                continue
            try:
                msg = json.loads(raw.decode("utf-8", errors="ignore").strip())
            except Exception:
                continue
            if msg.get("id") != req_id:
                continue
            if msg.get("status") != "ok":
                raise RuntimeError(f"bridge dmx error: {msg}")
            return
        raise RuntimeError("bridge dmx timeout")

    def send_frame(self, frame: bytes, universe=None):
        if frame is None:
            return
        payload_frame = bytes(frame)
        if len(payload_frame) == 512:
            payload_frame = b"\x00" + payload_frame
        if len(payload_frame) != 513:
            raise ValueError(f"frame length must be 512 or 513 bytes, got {len(payload_frame)}")

        req_id = f"dmx_{uuid.uuid4().hex[:8]}"
        payload = {
            "v": 1,
            "id": req_id,
            "op": "dmx_write",
            "universe": int(universe or 0),
            "frame_b64": base64.b64encode(payload_frame).decode("ascii"),
        }
        line = json.dumps(payload, separators=(",", ":")) + "\n"
        with self._lock:
            self._ensure_open()
            self.ser.write(line.encode("utf-8"))
            self.ser.flush()
            self._wait_ack(req_id)
