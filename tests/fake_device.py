"""A fake ZhiJinPower controller that answers like the real one (as far as known)."""
from __future__ import annotations

import asyncio

from custom_components.zhijin_mppt import protocol as p

ADDRESS = "AA:BB:CC:DD:EE:FF"
NAME = "ZJBE-AABBCCDDEEFF"


def with_crc(body: bytes) -> bytes:
    crc = p.crc16_modbus(body)
    return body + bytes([crc & 0xFF, crc >> 8])


class FakeController:
    """State of a controller. Unknown frames get no answer, like the real device."""

    def __init__(self) -> None:
        # settings block, register address -> raw value
        self.reg = {
            0x1001: 2,  # battery type: gel (b02)
            0x1002: 0,
            0x1003: 0,
            0x1004: 145,  # floating 14.5 V
            0x1005: 0,  # load mode (menu 5): 0 manual / Cot
            0x1006: 108,  # cut-off 10.8 V
            0x1007: 1,  # load on
            0x1008: 0,
            0x1009: 126,  # recovery 12.6 V
        }
        # status block, 10 registers (address 1..10). Index 6 is the actual load
        # output, which lags behind the load setting on the real controller.
        self.status = [2, 124, 0, 1, 2060, 0, 1, 0, 7987, 3]
        self.apply_writes = True  # False: acknowledge but ignore writes
        self.silent = False  # True: never answer
        self.split = False  # True: deliver replies in 20 byte chunks
        self.log: list[str] = []

    def status_frame(self) -> bytes:
        return with_crc(bytes([1, 3, 20]) + b"".join(v.to_bytes(2, "big") for v in self.status))

    def settings_frame(self) -> bytes:
        regs = [self.reg[p.SETTINGS_FIRST_REGISTER + i] for i in range(p.SETTINGS_REGISTER_COUNT)]
        return with_crc(bytes([1, 3, 18]) + b"".join(v.to_bytes(2, "big") for v in regs))

    def handle(self, frame: bytes) -> bytes | None:
        if self.silent:
            return None
        if frame == p.REQUEST:
            self.log.append("status")
            return self.status_frame()
        if frame == p.SETTINGS_REQUEST:
            self.log.append("settings")
            return self.settings_frame()
        if (
            len(frame) == 11
            and frame[1] == 0x10
            and p.crc16_modbus(frame[:-2]) == frame[-2] | frame[-1] << 8
        ):
            register = frame[2] << 8 | frame[3]
            value = int.from_bytes(frame[7:9], "big")
            self.log.append(f"write {register:04X}={value}")
            if self.apply_writes:
                self.reg[register] = value
            return with_crc(frame[:6])
        self.log.append("unknown")
        return None


class FakeClient:
    """Minimal stand-in for BleakClientWithServiceCache."""

    def __init__(self, controller: FakeController) -> None:
        self.controller = controller
        self.callback = None
        self.disconnected = False

    async def start_notify(self, uuid, callback) -> None:
        self.callback = callback

    async def stop_notify(self, uuid) -> None:
        pass

    async def disconnect(self) -> None:
        self.disconnected = True

    async def write_gatt_char(self, uuid, data, response=None) -> None:
        reply = self.controller.handle(bytes(data))
        if reply is None:
            return
        chunks = [reply[:20], reply[20:]] if self.controller.split and len(reply) > 20 else [reply]
        loop = asyncio.get_running_loop()
        for i, chunk in enumerate(chunks):
            loop.call_later(0.005 * (i + 1), self.callback, None, bytearray(chunk))
