import logging
import time

logger = logging.getLogger("pi.dmx.uart")


class UARTRS485Driver:
    def __init__(self, device: str = None):
        self.device = device
        self.last_frame = None
        self._opened = False

    def open(self):
        # best-effort: attempt to import serial
        try:
            import serial
            self.ser = serial.Serial(self.device or '/dev/serial0', baudrate=250000, bytesize=8, parity='N', stopbits=2, timeout=1)
            self._opened = True
        except Exception:
            logger.warning("pyserial not available or failed to open %s; driver in noop mode", self.device)
            self.ser = None
            self._opened = False

    def close(self):
        try:
            if getattr(self, 'ser', None):
                self.ser.close()
        except Exception:
            pass

    def send_frame(self, frame: bytes) -> bool:
        self.last_frame = frame
        if not self._opened or not getattr(self, 'ser', None):
            # noop but simulate success
            logger.info("Driver noop send_frame, len=%d", len(frame))
            return True
        try:
            # send break: pyserial supports send_break
            try:
                self.ser.break_condition = True
                time.sleep(0.0001)
                self.ser.break_condition = False
            except Exception:
                try:
                    self.ser.send_break()
                except Exception:
                    logger.warning("unable to send break on serial device")
            # write frame
            self.ser.write(frame)
            self.ser.flush()
            return True
        except Exception as e:
            logger.exception("Failed sending DMX frame: %s", e)
            return False
# UART RS485 driver
