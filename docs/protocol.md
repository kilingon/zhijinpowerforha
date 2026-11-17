# ZhiJinPower BLE protocol (reverse engineered)

Derived from Bluetooth HCI logs of the ZhiJinPower phone app and tests against a BL917-type 12 V controller. Not official; use at your own risk.

## Transport
- Advertised name `ZJBE-<12 hex MAC>`, service UUID `0000ff00-0000-1000-8000-00805f9b34fb`.
- GATT service `6E400001-B5A3-F393-E0A9-E50E24DCCA9E` (Nordic UART style):
  - `6E400002-…` notify (enable the CCCD),
  - `6E400003-…` write without response.
- The controller accepts **one** connection at a time (phone app and Home Assistant exclude each other).
- Replies arrive as one notification or as 20-byte chunks; buffer until the expected length.
- Only the exact frames below are answered; anything else gets no reply.

## Framing
Modbus-RTU style: `addr func … crc16`, CRC16 poly 0xA001, init 0xFFFF, low byte first. Device address is `01`.

## Reads
| Purpose | Frame | Reply |
|---|---|---|
| Status | `01 03 00 01 00 10 15 C6` | 25 bytes, 10 registers (addr 1..10) |
| Settings | `01 03 10 01 00 0F 50 CE` | 23 bytes, 9 registers (0x1001..0x1009) |

### Status registers (addr 1..10)
| Addr | Meaning |
|---|---|
| 2 | battery voltage, ×0.1 V |
| 3 | charge current, ×0.1 A (unverified) |
| 4 | load current, ×0.1 A |
| 5 | temperature, ×0.01 °C, signed |
| 7 | actual load output (lags a command by seconds) |
| 9 | total generation, ×0.1 Ah |
| 10 | generation counter. The app shows total = counter × 1000 + addr 9 (from the app's code, unverified on hardware) |
| 6 | photovoltaic state as shown by the app: 0 night, 1 day |
| 8 | wind input state (0 = closed) |
| 1 | controller type code (2 on the tested unit) |

### Settings registers
| Reg | Meaning | Writable range (raw) |
|---|---|---|
| 0x1001 | battery type: 1 lithium, 2 gel, 3 lead-acid/LiFePO4 | 1–3 (the app writes it the same way) |
| 0x1002 | timing mode hours (app list 0–12) | 0–12 (untested from Home Assistant) |
| 0x1004 | floating charge voltage ×0.1 V | 120–145 |
| 0x1006 | discharge cut-off ×0.1 V | 90–115 |
| 0x1007 | load on/off (takes effect immediately) | 0–1 |
| 0x1009 | discharge recovery ×0.1 V | 110–130 |
| 0x1005 | load mode (menu 5): 0 Cot (app: Manual), 1 Auto (Automatic), 2 Time (Timing), 3 Out (Straight out). The load switch (0x1007) is expected to work in Cot only | 0–3 (untested from Home Assistant) |
| 0x1008 | system voltage mode: 0 Auto, 1 12 V. The app lists 24, 36, 48, 60, 72, 84 and 96 V too; codes 2..8 are the presumed order and unverified | 0–1 |
| 0x1003 | timing mode minutes (app list 0–60) | 0–60 (untested from Home Assistant) |

The voltage ranges are the 12 V values from the BL917 manual; 24 V systems are not supported.

## Write
Function 0x10, one register: `01 10 hh ll 00 01 02 vh vl crc`. The acknowledgement is the first 6 bytes echoed plus CRC (8 bytes). The app reads settings, writes, then reads settings again; the integration does the same and verifies the value.

## Clock (not used by the integration)
The app sets the controller clock with a write to slave 0 (broadcast style): `00 10 10 09 00 14 21 hh mm 00 …` followed by a fixed tail and the CRC, 20 registers. Two captures (22:32 and 22:40) differ only in the hour/minute bytes (`0x16 0x20`, `0x16 0x28`) and the CRC. The clock is read back with `00 03 10 09 00 14 90 D6`. The app also sends slave 0 frames `00 03 00 01 00 05 D5 D8` (device information, ASCII id) and `00 03 00 01 00 10 14 17` (no reply).

Battery level in the app is a voltage estimate: 12 V pack when V <= 17 (else 24 V), `(V - 9n) / (12.6n - 9n)` clamped to 0..100 with n = 1 or 2. Solar power is battery voltage x charge current.

Thanks to [wescom-code/zhijinpower_ble](https://github.com/wescom-code/zhijinpower_ble) (MIT), whose notes on the app's registers helped to complete this map.
