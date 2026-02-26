import json
import threading
import time
import uuid

try:
    import serial
except Exception:  # pragma: no cover - optional dependency
    serial = None

try:
    from provision_bridge_pi_gpio import GpioBridgeError, ProvisionBridgeClient
except Exception:  # pragma: no cover - optional dependency
    GpioBridgeError = None
    ProvisionBridgeClient = None


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


def _prepare_payload(payload: dict):
    req = dict(payload or {})
    req_id = req.get("id") or f"prov_{uuid.uuid4().hex[:8]}"
    req["id"] = req_id
    req["v"] = req.get("v", 1)
    return req, req_id


def _call_bridge_gpio(
    port: str,
    baud: int,
    payload: dict,
    timeout_s: float,
    reset_pin=None,
    boot_pin=None,
    reset_active_low: bool = True,
    boot_active_low: bool = True,
    auto_reset: bool = False,
):
    if ProvisionBridgeClient is None:
        raise BridgeError(
            "GPIO bridge support unavailable (module `provision_bridge_pi_gpio.py` not importable)"
        )
    req, _ = _prepare_payload(payload)
    op = str(req.get("op") or "request")
    with _LOCK:
        try:
            with ProvisionBridgeClient(
                port=port,
                baud=baud,
                timeout=0.5,
                reset_pin=reset_pin,
                boot_pin=boot_pin,
                reset_active_low=bool(reset_active_low),
                boot_active_low=bool(boot_active_low),
                auto_reset=bool(auto_reset),
            ) as client:
                return client.call(op, req, timeout=float(timeout_s))
        except Exception as e:
            # Keep one error shape for API handlers.
            if GpioBridgeError is not None and isinstance(e, GpioBridgeError):
                raise BridgeError(str(e))
            raise BridgeError(f"gpio bridge failed: {e}")


def call_bridge(
    port: str,
    baud: int,
    payload: dict,
    timeout_s: float = 8.0,
    reset_pin=None,
    boot_pin=None,
    reset_active_low: bool = True,
    boot_active_low: bool = True,
    auto_reset: bool = False,
):
    if not port:
        raise BridgeError("bridge port not configured")

    use_gpio = reset_pin is not None or boot_pin is not None or bool(auto_reset)
    if use_gpio:
        return _call_bridge_gpio(
            port=port,
            baud=baud,
            payload=payload,
            timeout_s=timeout_s,
            reset_pin=reset_pin,
            boot_pin=boot_pin,
            reset_active_low=reset_active_low,
            boot_active_low=boot_active_low,
            auto_reset=auto_reset,
        )

    req, req_id = _prepare_payload(payload)
    line = json.dumps(req) + "\n"
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
