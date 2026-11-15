# Changelog

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
