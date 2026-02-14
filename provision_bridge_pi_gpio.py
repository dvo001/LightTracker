"""
Raspberry Pi GPIO/UART variant of the ESP-NOW provisioning bridge client.

This keeps the same NDJSON request/response protocol as provision_bridge.py,
but defaults to the Pi UART mapped to GPIO14/GPIO15 (`/dev/serial0`).

Optional reset/boot pin control is available when `lgpio` or `RPi.GPIO` is
installed, for wiring an ESP directly to Pi GPIO pins.
"""
import json
import threading
import time
import uuid

import serial

try:
    import lgpio  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    lgpio = None

try:
    import RPi.GPIO as GPIO  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    GPIO = None


class GpioBridgeError(RuntimeError):
    pass


class _PinController:
    def __init__(
        self,
        reset_pin=None,
        boot_pin=None,
        reset_active_low=True,
        boot_active_low=True,
    ):
        self.reset_pin = reset_pin
        self.boot_pin = boot_pin
        self.reset_active_low = bool(reset_active_low)
        self.boot_active_low = bool(boot_active_low)
        self._backend = "none"
        self._chip = None
        self._pins = [p for p in (self.reset_pin, self.boot_pin) if p is not None]

        if not self._pins:
            return

        if lgpio is not None:
            self._backend = "lgpio"
            self._chip = lgpio.gpiochip_open(0)
            for pin in self._pins:
                level = self._default_level(pin)
                lgpio.gpio_claim_output(self._chip, pin, level)
            return

        if GPIO is not None:
            self._backend = "rpi"
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            for pin in self._pins:
                level = self._default_level(pin)
                GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH if level else GPIO.LOW)
            return

        raise GpioBridgeError(
            "GPIO pins requested but no backend found. Install lgpio or RPi.GPIO."
        )

    def _to_level(self, asserted, active_low):
        if active_low:
            return 0 if asserted else 1
        return 1 if asserted else 0

    def _default_level(self, pin):
        if pin == self.reset_pin:
            # keep reset released
            return self._to_level(asserted=False, active_low=self.reset_active_low)
        # keep boot strap in normal-run state
        return self._to_level(asserted=False, active_low=self.boot_active_low)

    def _write(self, pin, level):
        if self._backend == "none" or pin is None:
            return
        if self._backend == "lgpio":
            lgpio.gpio_write(self._chip, pin, 1 if level else 0)
            return
        GPIO.output(pin, GPIO.HIGH if level else GPIO.LOW)

    def set_bootloader_mode(self, enabled):
        if self.boot_pin is None:
            return
        level = self._to_level(asserted=bool(enabled), active_low=self.boot_active_low)
        self._write(self.boot_pin, level)

    def pulse_reset(self, pulse_s=0.05, settle_s=0.15):
        if self.reset_pin is None:
            return
        assert_level = self._to_level(asserted=True, active_low=self.reset_active_low)
        release_level = self._to_level(asserted=False, active_low=self.reset_active_low)
        self._write(self.reset_pin, assert_level)
        time.sleep(float(pulse_s))
        self._write(self.reset_pin, release_level)
        time.sleep(float(settle_s))

    def cleanup(self):
        if self._backend == "lgpio" and self._chip is not None:
            try:
                for pin in self._pins:
                    lgpio.gpio_free(self._chip, pin)
            finally:
                lgpio.gpiochip_close(self._chip)
            self._chip = None
            return
        if self._backend == "rpi":
            try:
                for pin in self._pins:
                    GPIO.cleanup(pin)
            except Exception:
                pass


class ProvisionBridgeClient:
    def __init__(
        self,
        port="/dev/serial0",
        baud=115200,
        timeout=1.0,
        reset_pin=None,
        boot_pin=None,
        reset_active_low=True,
        boot_active_low=True,
        auto_reset=False,
    ):
        self.ser = serial.Serial(
            port,
            baudrate=baud,
            timeout=timeout,
            write_timeout=1,
            rtscts=False,
            dsrdtr=False,
        )
        self.lock = threading.Lock()
        self.gpio = _PinController(
            reset_pin=reset_pin,
            boot_pin=boot_pin,
            reset_active_low=reset_active_low,
            boot_active_low=boot_active_low,
        )

        # Avoid accidental auto-reset on adapters that expose control lines.
        try:
            self.ser.dtr = False
            self.ser.rts = False
        except Exception:
            pass

        if auto_reset:
            self.reset_target()

        try:
            self.ser.reset_input_buffer()
        except Exception:
            pass

    def close(self):
        try:
            self.ser.close()
        finally:
            self.gpio.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def _send(self, obj):
        line = json.dumps(obj) + "\n"
        self.ser.write(line.encode("utf-8"))
        self.ser.flush()

    def _recv(self, req_id, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.ser.readline()
            if not line:
                continue
            try:
                msg = json.loads(line.decode("utf-8", errors="ignore").strip())
            except Exception:
                continue
            if msg.get("id") == req_id:
                return msg
        return None

    def call(self, op, payload, timeout=5.0):
        req = dict(payload or {})
        req.setdefault("op", op)
        req_id = req.get("id") or str(uuid.uuid4())
        req["id"] = req_id
        req["v"] = req.get("v", 1)
        with self.lock:
            self._send(req)
            return self._recv(req_id, timeout)

    def hello(self):
        return self.call(
            "hello",
            {
                "op": "hello",
                "client": "provision_server",
                "cap": ["provision", "readback", "reboot"],
            },
            timeout=2.0,
        )

    def provision_write(self, device_id, token, cfg, apply=True, reboot=True, timeout_ms=8000):
        return self.call(
            "provision_write",
            {
                "op": "provision_write",
                "device_id": device_id,
                "auth": {"token": token},
                "cfg": cfg,
                "apply": bool(apply),
                "reboot": bool(reboot),
                "timeout_ms": int(timeout_ms),
            },
            timeout=max(5.0, timeout_ms / 1000.0 + 2.0),
        )

    def provision_read(self, device_id, token, fields, timeout_ms=5000):
        return self.call(
            "provision_read",
            {
                "op": "provision_read",
                "device_id": device_id,
                "auth": {"token": token},
                "fields": list(fields or []),
                "timeout_ms": int(timeout_ms),
            },
            timeout=max(5.0, timeout_ms / 1000.0 + 2.0),
        )

    def reboot(self, device_id, token, mode="normal", timeout_ms=4000):
        return self.call(
            "reboot",
            {
                "op": "reboot",
                "device_id": device_id,
                "auth": {"token": token},
                "mode": mode,
                "timeout_ms": int(timeout_ms),
            },
            timeout=max(5.0, timeout_ms / 1000.0 + 2.0),
        )

    def enter_bootloader(self):
        self.gpio.set_bootloader_mode(True)
        self.gpio.pulse_reset()

    def reset_target(self):
        self.gpio.set_bootloader_mode(False)
        self.gpio.pulse_reset()


# Example usage:
# client = ProvisionBridgeClient("/dev/serial0")
# print(client.hello())
#
# Optional direct wiring with ESP reset/boot control:
# client = ProvisionBridgeClient("/dev/serial0", reset_pin=17, boot_pin=27, auto_reset=True)
