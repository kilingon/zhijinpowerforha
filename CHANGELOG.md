# Changelog

## 0.5.3
- **New:** system voltage mode (register 0x1008) as a sensor and as a select (disabled by default). Only Auto and 12 V can be set; 24, 36, 48, 60, 72 and 84 V are shown by the sensor (presumed order, unverified) but never written.
- **New:** voltage settings are no longer written when the system voltage mode is not Auto or 12 V, because the limits are for 12 V systems.
- **New:** "Photovoltaic state" sensor (night / day) from status register 6.
- **Changed:** load mode names follow the controller and the app: Manual (Cot), Automatic (Auto), Timing (Time), Straight out (Out). The internal state keys are unchanged.
- **Verified from a capture of the app:** the battery type write (0x1001) uses the same frame the integration sends.
- The unknown-register sensor "Setting 0x1008" is gone (replaced by the system voltage sensors).
- Tests (82 in total).

## 0.5.2
- **New:** option "Bluetooth adapter / proxy": connect only through one chosen adapter or ESP32 proxy instead of letting Home Assistant switch between several. If the chosen one cannot hear the controller, the entities become unavailable (set it back to Auto to undo).
- **New:** connection diagnostic sensors that stay available when the controller cannot be reached: last update, failed polls in a row, last error, Bluetooth source and signal strength (RSSI).
- **Changed:** a single failed poll no longer makes every entity unavailable. The last values are kept, and the entities become unavailable after 3 failed polls in a row. From then on the polling backs off (up to 5 minutes) until the controller answers again.
- Tests for all of the above (79 in total).

## 0.5.1
- Fix hassfest: the translation text no longer contains `<address>` (read as HTML).
- Add the integration icon (`brand/icon.png`) required by HACS.
- GitHub workflows use `actions/checkout@v5`.

## 0.5.0
- **Fixed:** the load mode is register 0x1005 (menu 5 on the controller), not 0x1002. The "Load mode" sensor now shows Manual (Cot) / Auto / Timer / Out. 0x1002 is exposed as a disabled diagnostic sensor.
- **New:** "Load mode setting" select (disabled by default, write not verified on hardware).
- **New:** the load switch refuses to act when the load mode is not manual (Cot) and says why, because the controller drives the output itself in the other modes.
- Tests for the load mode (74 in total).

## 0.4.2
- **Fixed:** the Bluetooth connection is always released. Closing is shielded against cancellation and has timeouts, so a hanging disconnect cannot keep the controller occupied (it accepts one connection and stops advertising while connected).
- Default polling interval is now 60 s (was 30 s). Existing entries keep their configured value.
- `manifest.json` no longer starts with a byte order mark.

## 0.4.1
- Fix `manifest.json` encoding (BOM) that made Home Assistant's marketplace fail with "Unknown error".

## 0.4.0
- First public version: Bluetooth discovery, manual MAC entry, connection test, options flow (polling interval), diagnostics, translations (en, tr), tests, HACS/hassfest workflows.
