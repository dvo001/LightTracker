import socket
from typing import Optional


class ArtnetDriver:
    def __init__(self, target_ip: str = "255.255.255.255", port: int = 6454, default_universe: int = 0):
        self.target_ip = target_ip
        self.port = port
        self.default_universe = default_universe
        self.sock: Optional[socket.socket] = None
        self.sequence = 1

    def init(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except Exception:
            pass
        self.sock.setblocking(False)

    def _build_packet(self, universe: int, frame: bytes) -> bytes:
        data = frame[1:513]
        if len(data) > 512:
            data = data[:512]
        data_len = len(data)

        header = bytearray()
        header.extend(b"Art-Net\x00")
        header.extend((0x00, 0x50))  # OpOutput / ArtDMX
        header.extend((0x00, 0x0e))  # ProtVer 14
        header.append(self.sequence & 0xFF)
        header.append(0x00)  # physical
        header.extend((universe & 0xFF, (universe >> 8) & 0xFF))
        header.extend(((data_len >> 8) & 0xFF, data_len & 0xFF))
        header.extend(data)
        self.sequence = (self.sequence + 1) % 256 or 1
        return bytes(header)

    def send_frame(self, frame: bytes, universe: Optional[int] = None):
        if not self.sock:
            self.init()
        if not self.sock:
            return
        uni = self.default_universe if universe is None else universe
        packet = self._build_packet(uni, frame)
        try:
            self.sock.sendto(packet, (self.target_ip, self.port))
        except Exception:
            pass
