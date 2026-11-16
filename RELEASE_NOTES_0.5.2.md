## 0.5.2
- New: option "Bluetooth adapter / proxy" to pin one adapter or ESP32 proxy.
- New: connection diagnostic sensors (last update, failed polls, last error, Bluetooth source, signal strength).
- Changed: a single failed poll keeps the last values; entities become unavailable after 3 failed polls in a row and polling backs off until the controller answers.
- Includes 0.5.0 and 0.5.1 (load mode fix and select, HACS/hassfest fixes).

Full list: CHANGELOG.md
