"""Protocol tests with frames captured from a real controller."""
import pytest

from custom_components.zhijin_mppt import protocol as p
from custom_components.zhijin_mppt.config_flow import normalize_address


def h(text: str) -> bytes:
    return bytes.fromhex(text.replace(" ", ""))


def _frame(regs, function_length=20):
    body = bytes([1, 3, function_length]) + b"".join(r.to_bytes(2, "big") for r in regs)
    crc = p.crc16_modbus(body)
    return body + bytes([crc & 255, crc >> 8])


def test_crc_of_known_requests():
    for frame in (p.REQUEST, p.SETTINGS_REQUEST):
        assert p.crc16_modbus(frame[:-2]) == frame[-2] | frame[-1] << 8


def test_status_reply():
    data = p.parse_response(h("01 03 14 00 02 00 7e 00 00 00 00 08 16 00 00 00 00 00 00 1f 33 00 03 87 2a"))
    assert data["battery_voltage"] == 12.6
    assert data["temperature"] == 20.7
    assert data["total_generation"] == 798.7
    assert data["load_on"] is False
    assert data["load_current"] == 0.0


def test_status_reply_with_load_current():
    data = p.parse_response(_frame([2, 121, 0, 1, 2060, 0, 1, 0, 7987, 3]))
    assert data["battery_voltage"] == 12.1
    assert data["load_current"] == 0.1
    assert data["load_on"] is True


def test_negative_temperature():
    data = p.parse_response(_frame([2, 124, 0, 0, 0x10000 - 550, 0, 1, 0, 0, 3]))
    assert data["temperature"] == -5.5


def test_settings_reply():
    data = p.parse_settings(h("01 03 12 00 02 00 00 00 00 00 91 00 00 00 6c 00 01 00 00 00 7e bb fa"))
    assert data["float_voltage"] == 14.5
    assert data["cutoff_voltage"] == 10.8
    assert data["recovery_voltage"] == 12.6
    assert data["battery_type"] == 2
    assert data["battery_type_name"] == "gel"
    assert data["load_mode_name"] == "manual"
    assert data["load_setting"] is True
    off = p.parse_settings(h("01 03 12 00 02 00 00 00 00 00 91 00 00 00 6c 00 00 00 00 00 7e 86 3a"))
    assert off["load_setting"] is False


def test_unknown_codes_are_none():
    data = p.parse_settings(_frame([9, 0, 0, 145, 5, 108, 1, 0, 126], 18))
    assert data["battery_type"] == 9 and data["battery_type_name"] is None
    assert data["load_mode"] == 5 and data["load_mode_name"] is None


@pytest.mark.parametrize(
    "frame",
    [
        "01 03 14 00 02 00 7e 00 00 00 00 08 16 00 00 00 00 00 00 1f 33 00 03 87 2b",  # bad CRC
        "01 03 14 00 02 00 7e",  # short
        "02 03 14 00 02 00 7e 00 00 00 00 08 16 00 00 00 00 00 00 1f 33 00 03 87 2a",  # wrong slave
    ],
)
def test_bad_status_replies_are_rejected(frame):
    with pytest.raises(ValueError):
        p.parse_response(h(frame))


@pytest.mark.parametrize(
    ("register", "ack"),
    [
        (0x1004, "01 10 10 04 00 01 44 c8"),
        (0x1006, "01 10 10 06 00 01 e5 08"),
        (0x1007, "01 10 10 07 00 01 b4 c8"),
        (0x1009, "01 10 10 09 00 01 d5 0b"),
    ],
)
def test_real_write_acknowledgements(register, ack):
    p.parse_write_ack(h(ack), register)
    with pytest.raises(ValueError):
        p.parse_write_ack(h(ack), register + 1)


def test_load_frames_equal_the_ones_sent_by_the_app():
    assert p.build_load_frame(True) == h("01 10 10 07 00 01 02 00 01 77 e6")
    assert p.build_load_frame(False) == h("01 10 10 07 00 01 02 00 00 b6 26")


@pytest.mark.parametrize(
    ("register", "value"),
    [
        (0x1004, 146), (0x1004, 119), (0x1006, 116), (0x1006, 89), (0x1009, 131), (0x1009, 109),
        (0x1001, 0), (0x1001, 4), (0x1007, 2),
        (0x1002, 0), (0x1003, 0), (0x0001, 0), (0x2000, 1),
    ],
)
def test_writes_outside_the_known_ranges_are_refused(register, value):
    with pytest.raises(ValueError):
        p.build_write_frame(register, value)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("AA:BB:CC:DD:EE:FF", "AA:BB:CC:DD:EE:FF"),
        ("aa:bb:cc:dd:ee:ff", "AA:BB:CC:DD:EE:FF"),
        ("aa-bb-cc-dd-ee-ff", "AA:BB:CC:DD:EE:FF"),
        ("AABBCCDDEEFF", "AA:BB:CC:DD:EE:FF"),
        ("  aabbccddeeff  ", "AA:BB:CC:DD:EE:FF"),
        ("ZJBE-AABBCCDDEEFF", "AA:BB:CC:DD:EE:FF"),
        ("zjbx-aabbccddeeff", "AA:BB:CC:DD:EE:FF"),
        ("", None),
        ("hello", None),
        ("AA:BB:CC:DD:EE", None),
        ("AA:BB:CC:DD:EE:GG", None),
        ("AABBCCDDEEFF00", None),
        ("OTHER-AABBCCDDEEFF", None),
    ],
)
def test_normalize_address(text, expected):
    assert normalize_address(text) == expected


def test_load_mode_codes_and_write_frame():
    assert p.LOAD_MODES == {0: "manual", 1: "auto", 2: "timer", 3: "output"}
    frame = p.build_write_frame(p.REG_LOAD_MODE, 2)
    assert frame[:9] == bytes.fromhex("01 10 10 05 00 01 02 00 02")
    with pytest.raises(ValueError):
        p.build_write_frame(p.REG_LOAD_MODE, 4)


def test_system_voltage_and_pv_state():
    assert p.SYSTEM_VOLTAGES[0] == "auto" and p.SYSTEM_VOLTAGES[1] == "12v"
    data = p.parse_settings(_frame([2, 0, 0, 145, 0, 108, 1, 1, 126], 18))
    assert data["system_voltage"] == 1 and data["system_voltage_name"] == "12v"
    assert p.parse_settings(_frame([2, 0, 0, 145, 0, 108, 1, 9, 126], 18))["system_voltage_name"] is None
    assert p.build_write_frame(p.REG_SYSTEM_VOLTAGE, 1)[:9] == bytes.fromhex("01 10 10 08 00 01 02 00 01")
    # only Auto and 12 V may be written
    with pytest.raises(ValueError):
        p.build_write_frame(p.REG_SYSTEM_VOLTAGE, 2)
    day = p.parse_response(_frame([2, 124, 0, 0, 2060, 1, 0, 0, 7987, 3]))
    night = p.parse_response(_frame([2, 124, 0, 0, 2060, 0, 0, 0, 7987, 3]))
    odd = p.parse_response(_frame([2, 124, 0, 0, 2060, 5, 0, 0, 7987, 3]))
    assert (day["pv_state"], night["pv_state"], odd["pv_state"]) == ("day", "night", None)
