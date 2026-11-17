"""Protocol helpers for ZhiJinPower (ZJBE/ZJBX/ZJBW) Bluetooth MPPT controllers.

Reverse engineered from Bluetooth HCI captures of the ZhiJinPower app and
confirmed with direct tests against a controller. The controller exposes a
Nordic-UART-like GATT service. Notifications are enabled on the "notify"
characteristic and Modbus-RTU-style frames are written to the "write" one.

Known frames:
* read  0x0001 (status block, 10 registers)   -> measurements, answered with 25 bytes
* read  0x1001 (settings block, 9 registers)  -> settings, answered with 23 bytes
* write one register with function 0x10       -> answered with an 8 byte echo

The controller replies with a fixed number of registers whatever quantity is
requested, and ignores frames it does not know, so only the exact frames above
are used.
"""
from __future__ import annotations

from typing import Any

NOTIFY_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
WRITE_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

# --- status block -------------------------------------------------------------
# slave 1, function 3, start address 1, quantity 16, CRC (lo, hi)
REQUEST = bytes.fromhex("01030001001015C6")
REGISTER_COUNT = 10
RESPONSE_LENGTH = 3 + 2 * REGISTER_COUNT + 2  # 25 bytes

# --- settings block -----------------------------------------------------------
# slave 1, function 3, start address 0x1001, quantity 15, CRC
SETTINGS_REQUEST = bytes.fromhex("01031001000F50CE")
SETTINGS_FIRST_REGISTER = 0x1001
SETTINGS_REGISTER_COUNT = 9
SETTINGS_LENGTH = 3 + 2 * SETTINGS_REGISTER_COUNT + 2  # 23 bytes

REG_BATTERY_TYPE = 0x1001  # 1 lithium (b01), 2 gel (b02), 3 lead-acid/LiFePO4 (b03)
REG_LOAD_MODE = 0x1005  # menu 5, load mode: 0 Cot (manual), 1 Auto, 2 Time, 3 Out
REG_FLOAT_VOLTAGE = 0x1004  # tenths of a volt
REG_CUTOFF_VOLTAGE = 0x1006  # discharge cut-off, tenths of a volt
REG_TIMER_HOURS = 0x1002  # timing mode: hours (0..12), from the app's value list
REG_TIMER_MINUTES = 0x1003  # timing mode: minutes (0..60)
REG_LOAD = 0x1007  # 1 = load on, 0 = load off
REG_RECOVERY_VOLTAGE = 0x1009  # discharge recovery, tenths of a volt
REG_SYSTEM_VOLTAGE = 0x1008  # system voltage mode: 0 Auto, 1 12 V (the app lists up to 84 V)
LOAD_REGISTER = REG_LOAD

# Keys are translated in translations/*.json (entity.select.battery_type.state ...)
BATTERY_TYPES = {1: "lithium", 2: "gel", 3: "lead_acid"}
# Seen in the app's value list and in two other projects, never seen on a controller
# here: shown by the sensor but never written.
BATTERY_TYPES_READ_ONLY = {
    4: "open_lead_acid", 5: "ternary_lithium", 6: "lifepo4", 7: "flooded",
}
ALL_BATTERY_TYPES = {**BATTERY_TYPES, **BATTERY_TYPES_READ_ONLY}
LOAD_MODES = {0: "manual", 1: "auto", 2: "timer", 3: "output"}
# Only 0 (Auto) and 1 (12 V) were seen in a capture of the app. The app also offers
# 24, 36, 48, 60, 72, 84 and 96 V; the codes 2..8 are the presumed order and unverified,
# so they are shown but never written.
SYSTEM_VOLTAGES = {
    0: "auto", 1: "12v", 2: "24v", 3: "36v", 4: "48v", 5: "60v", 6: "72v", 7: "84v",
    8: "96v",
}
WRITABLE_SYSTEM_VOLTAGES = (0, 1)
# Status register 6: photovoltaic state as shown by the app (0 night, 1 day)
PV_STATES = {0: "night", 1: "day"}
# The voltage limits below are for 12 V systems only, so voltages are only written
# while the system voltage mode is one of these (Auto picks 12 V for a 12 V battery).
VOLTAGE_WRITE_MODES = (0, 1)

# Registers that may be written and the accepted raw range. The voltage limits
# are the 12 V values from the controller manual (BL917), in tenths of a volt.
WRITABLE: dict[int, tuple[int, int]] = {
    REG_BATTERY_TYPE: (1, 3),
    REG_TIMER_HOURS: (0, 12),
    REG_TIMER_MINUTES: (0, 60),
    REG_FLOAT_VOLTAGE: (120, 145),
    REG_CUTOFF_VOLTAGE: (90, 115),
    REG_LOAD: (0, 1),
    REG_LOAD_MODE: (0, 3),
    REG_SYSTEM_VOLTAGE: (0, 1),
    REG_RECOVERY_VOLTAGE: (110, 130),
}
ACK_LENGTH = 8


def battery_percent(voltage: float) -> int:
    """Battery level the way the phone app computes it (a voltage based estimate).

    Up to 17 V the pack is treated as 12 V, above that as 24 V, linear between
    9 V and 12.6 V per 12 V block and clamped to 0..100.
    """
    blocks = 1 if voltage <= 17 else 2
    percent = (voltage - 9 * blocks) / (12.6 * blocks - 9 * blocks) * 100
    return round(max(0, min(100, percent)))


def crc16_modbus(data: bytes) -> int:
    """Return the Modbus CRC16 of data."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def _registers(frame: bytes, length: int, count: int) -> list[int]:
    """Validate a read reply and return its registers."""
    if len(frame) < length:
        raise ValueError(f"short frame: {len(frame)} bytes")
    frame = bytes(frame[:length])
    if frame[0] != 0x01 or frame[1] != 0x03 or frame[2] != 2 * count:
        raise ValueError(f"unexpected header: {frame[:3].hex(' ')}")
    if (frame[-2] | (frame[-1] << 8)) != crc16_modbus(frame[:-2]):
        raise ValueError("CRC mismatch")
    return [int.from_bytes(frame[3 + 2 * i : 5 + 2 * i], "big") for i in range(count)]


def parse_response(frame: bytes) -> dict[str, Any]:
    """Parse the 25 byte status reply. Raises ValueError if it is invalid."""
    regs = _registers(frame, RESPONSE_LENGTH, REGISTER_COUNT)

    temperature_raw = regs[4]
    if temperature_raw >= 0x8000:  # allow sub-zero temperatures
        temperature_raw -= 0x10000

    battery_voltage = regs[1] / 10
    charge_current = regs[2] / 10
    resets = regs[9]
    return {
        # confirmed against the controller display / app
        "battery_voltage": battery_voltage,  # address 2, V
        "battery_percent": battery_percent(battery_voltage),  # app formula, estimate
        "solar_power": round(battery_voltage * charge_current, 1),  # W, V x I
        "load_current": regs[3] / 10,  # address 4, A
        "temperature": temperature_raw / 100,  # address 5, deg C
        # actual load output state. Lags behind a load switch command by several
        # seconds, use "load_setting" for the switch.
        "load_on": regs[6] == 1,  # address 7
        "total_generation": regs[8] / 10,  # address 9, Ah
        # The app shows total = counter x 1000 + address 9 (see docs/protocol.md).
        # Address 10 is that counter (it was once taken for a charge stage).
        "charge_resets": resets,  # address 10
        "total_generation_combined": resets * 1000 + regs[8] / 10,
        "charge_current": charge_current,  # address 3, A
        # wind input state (0 = closed), shown by the app
        "wind_on": regs[7] == 1,  # address 8
        "pv_day": regs[5] == 1,  # address 6
        # unknown registers, exposed as disabled diagnostic sensors
        "register_1": regs[0],
        "pv_state": PV_STATES.get(regs[5]),  # address 6, None if unknown
        "register_6": regs[5],
        "register_8": regs[7],
    }


def parse_settings(frame: bytes) -> dict[str, Any]:
    """Parse the 23 byte settings reply. Raises ValueError if it is invalid."""
    regs = _registers(frame, SETTINGS_LENGTH, SETTINGS_REGISTER_COUNT)
    return {
        "battery_type": regs[0],
        "battery_type_name": ALL_BATTERY_TYPES.get(regs[0]),  # None if unknown
        "load_mode": regs[4],  # 0x1005
        "load_mode_name": LOAD_MODES.get(regs[4]),  # None if unknown
        "float_voltage": regs[3] / 10,
        "cutoff_voltage": regs[5] / 10,
        "recovery_voltage": regs[8] / 10,
        "load_setting": regs[6] == 1,  # commanded load state, updates at once
        "timer_hours": regs[1],  # 0x1002, used in Timing mode
        "timer_minutes": regs[2],  # 0x1003, used in Timing mode
        "system_voltage": regs[7],
        "system_voltage_name": SYSTEM_VOLTAGES.get(regs[7]),  # None if unknown
        "_settings_raw": {SETTINGS_FIRST_REGISTER + i: v for i, v in enumerate(regs)},
    }


def build_write_frame(register: int, value: int) -> bytes:
    """Return a "write one register" frame. Only known registers/ranges are allowed."""
    if register not in WRITABLE:
        raise ValueError(f"register 0x{register:04X} is not writable")
    low, high = WRITABLE[register]
    if not low <= value <= high:
        raise ValueError(f"value {value} outside {low}..{high} for 0x{register:04X}")
    body = bytes(
        [0x01, 0x10, register >> 8, register & 0xFF, 0x00, 0x01, 0x02]
    ) + value.to_bytes(2, "big")
    crc = crc16_modbus(body)
    return body + bytes([crc & 0xFF, crc >> 8])


def build_load_frame(on: bool) -> bytes:
    """Return the captured "load on/off" write frame."""
    return build_write_frame(REG_LOAD, 1 if on else 0)


def parse_write_ack(frame: bytes, register: int = REG_LOAD) -> None:
    """Validate the 8 byte acknowledgement of a one-register write."""
    if len(frame) < ACK_LENGTH:
        raise ValueError(f"short acknowledgement: {len(frame)} bytes")
    frame = bytes(frame[:ACK_LENGTH])
    expected = bytes([0x01, 0x10, register >> 8, register & 0xFF, 0x00, 0x01])
    if frame[:6] != expected:
        raise ValueError(f"unexpected acknowledgement: {frame.hex(' ')}")
    if (frame[6] | (frame[7] << 8)) != crc16_modbus(frame[:6]):
        raise ValueError("CRC mismatch in acknowledgement")
