import time
import json

try:
    import serial
except Exception:
    serial = None


class UartRs485Driver:
    def __init__(self, device: str = "/dev/serial0"):
        self.device = device
        self.ser = None

    def init(self):
        if serial is None:
            raise RuntimeError("pyserial not installed")
        self.ser = serial.Serial(self.device, baudrate=250000, bytesize=8, parity="N", stopbits=2)

    def send_frame(self, frame: bytes, universe=None):
        if not self.ser:
            self.init()
        # DMX break + MAB best-effort
        try:
            self.ser.break_condition = True
            time.sleep(88e-6)
            self.ser.break_condition = False
            time.sleep(8e-6)
        except Exception:
            # fallback: short sleep
            time.sleep(120e-6)
        self.ser.write(frame)
        self.ser.flush()
