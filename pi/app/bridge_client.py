import json
import threading
import time
import uuid

try:
    import serial
except Exception:  # pragma: no cover - optional dependency
    serial = None


_LOCK = threading.Lock()


class BridgeError(RuntimeError):
    pass


def _open_serial(port: str, baud: int, timeout_s: float):
    if serial is None:
        raise BridgeError("pyserial not installed")
    try:
        ser = serial.Serial(
            port,
            baudrate=baud,
            timeout=timeout_s,
            write_timeout=1,
            rtscts=False,
            dsrdtr=False,
        )
    except Exception as e:
        raise BridgeError(f"open failed: {e}")
    try:
        ser.dtr = False
        ser.rts = False
    except Exception:
        pass
    time.sleep(0.6)
    try:
        ser.reset_input_buffer()
    except Exception:
        pass
    return ser


def call_bridge(port: str, baud: int, payload: dict, timeout_s: float = 8.0):
    if not port:
        raise BridgeError("bridge port not configured")
    req_id = payload.get("id") or f"prov_{uuid.uuid4().hex[:8]}"
    payload["id"] = req_id
    payload["v"] = payload.get("v", 1)
    line = json.dumps(payload) + "\n"
    deadline = time.time() + timeout_s
    with _LOCK:
        ser = _open_serial(port, baud, timeout_s=0.5)
        try:
            ser.write(line.encode("utf-8"))
            ser.flush()
            while time.time() < deadline:
                raw = ser.readline()
                if not raw:
                    continue
                try:
                    msg = json.loads(raw.decode("utf-8", errors="ignore").strip())
                except Exception:
                    continue
                if msg.get("id") == req_id:
                    return msg
        finally:
            try:
                ser.close()
            except Exception:
                pass
    return None
