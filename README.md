# ZhiJinPower MPPT for Home Assistant

[Türkçe](README.tr.md)

Custom integration for Bluetooth LE MPPT solar charge controllers that use the **ZhiJinPower** phone app (BLE name `ZJBE-<MAC>`, BL917-type, 12 V). Local, no cloud.

## Features
- Battery voltage, load current, charge current (unverified), temperature, total generation
- **Load on/off switch**
- Settings as number entities: floating charge voltage (12.0–14.5 V), discharge recovery (11.0–13.0 V), discharge cut-off (9.0–11.5 V), limits taken from the manual
- Battery type (optional select, disabled by default)
- Works with any Home Assistant Bluetooth adapter or ESP32 Bluetooth proxy
- Diagnostics download (address redacted), polling interval option (10–600 s)

## Installation
**HACS:** HACS → ⋮ → Custom repositories → add `https://github.com/kilingon/zhijinpowerforha` as *Integration* → install → restart Home Assistant.

**Manual:** copy `custom_components/zhijin_mppt` into your `config/custom_components/` and restart.

## Setup
Settings → Devices & services → Add integration → *ZhiJinPower MPPT*.
1. If Home Assistant already sees the controller over Bluetooth, it is offered automatically (or choose it from the list).
2. Otherwise type the Bluetooth address (`AA:BB:CC:DD:EE:FF`, or the name `ZJBE-AABBCCDDEEFF`).

**Close the phone app first.** The controller accepts only one Bluetooth connection. Home Assistant connects briefly every poll (default 30 s), so the app can connect in between.

## Known limitations
- Tested on one 12 V BL917-type controller only. 24 V systems are not supported.
- Charge current scale, charge stage codes, load modes other than manual and the battery type write are unverified.
- The "Load output" sensor lags a switch command by several seconds; the switch shows the commanded state.
- Reverse-engineered protocol, see [docs/protocol.md](docs/protocol.md). Writing settings is at your own risk.

## Development
`pip install -r requirements_test.txt && pytest`

MIT licensed. Not affiliated with ZhiJinPower.
