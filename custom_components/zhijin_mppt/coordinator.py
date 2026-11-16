"""Data coordinator for the ZhiJinPower MPPT integration."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from bleak.backends.device import BLEDevice

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .connection import (
    COMMUNICATION_ERRORS,
    ZhiJinError,
    async_open_session,
)
from .const import (
    ADAPTER_AUTO,
    CONF_ADAPTER,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_BACKOFF_INTERVAL,
    MAX_TOLERATED_FAILURES,
)
from .protocol import (
    ACK_LENGTH,
    REG_LOAD,
    REQUEST,
    RESPONSE_LENGTH,
    SETTINGS_LENGTH,
    SETTINGS_REQUEST,
    build_write_frame,
    parse_response,
    parse_settings,
    parse_write_ack,
)

_LOGGER = logging.getLogger(__name__)

VERIFY_ATTEMPTS = 3  # read-backs after a write before it is called a failure
VERIFY_DELAY = 0.5  # seconds between read-backs


class ZhiJinCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the controller over Bluetooth and write its settings."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.data[CONF_ADDRESS]}",
            update_interval=timedelta(seconds=interval),
        )
        self.address: str = entry.data[CONF_ADDRESS]
        self.base_interval = interval
        self.preferred_source: str = entry.options.get(CONF_ADAPTER, ADAPTER_AUTO)
        # Diagnostics, shown as sensors
        self.failed_polls = 0
        self.last_success: datetime | None = None
        self.last_error: str | None = None
        self.bluetooth_source: str | None = None
        self.signal_strength: int | None = None
        # The controller accepts one connection at a time.
        self._lock = asyncio.Lock()

    def _get_ble_device(self) -> BLEDevice | None:
        """The BLEDevice to connect with, honouring the selected adapter / proxy."""
        if self.preferred_source != ADAPTER_AUTO:
            for found in bluetooth.async_scanner_devices_by_address(
                self.hass, self.address, connectable=True
            ):
                if found.scanner.source == self.preferred_source:
                    self.bluetooth_source = found.scanner.source
                    self.signal_strength = found.advertisement.rssi
                    return found.ble_device
            return None
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is not None:
            info = bluetooth.async_last_service_info(
                self.hass, self.address, connectable=True
            )
            if info is not None:
                self.bluetooth_source = info.source
                self.signal_strength = info.rssi
        return ble_device

    def _async_session(self, ble_device: BLEDevice):
        return async_open_session(
            ble_device, self.config_entry.title, self._get_ble_device
        )

    def _require_device(self) -> BLEDevice:
        ble_device = self._get_ble_device()
        if ble_device is None:
            if self.preferred_source != ADAPTER_AUTO:
                raise UpdateFailed(
                    f"{self.address} is not visible to the selected adapter or proxy "
                    f"{self.preferred_source}"
                )
            raise UpdateFailed(
                f"{self.address} is not in range of any Bluetooth adapter or proxy"
            )
        return ble_device

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self._async_fetch()
        except UpdateFailed as err:
            return self._handle_failure(err)
        self._record_success()
        return data

    async def _async_fetch(self) -> dict[str, Any]:
        ble_device = self._require_device()
        try:
            async with self._lock, self._async_session(ble_device) as session:
                status = await session.request(REQUEST, RESPONSE_LENGTH, parse_response)
                settings = await session.request(
                    SETTINGS_REQUEST, SETTINGS_LENGTH, parse_settings
                )
        except COMMUNICATION_ERRORS as err:
            raise UpdateFailed(f"Error talking to {self.address}: {err}") from err
        return {**status, **settings}

    def _record_success(self) -> None:
        if self.failed_polls:
            _LOGGER.info(
                "%s: reachable again after %s failed polls", self.address, self.failed_polls
            )
        self.failed_polls = 0
        self.last_error = None
        self.last_success = dt_util.utcnow()
        self.update_interval = timedelta(seconds=self.base_interval)

    def _handle_failure(self, err: UpdateFailed) -> dict[str, Any]:
        """Keep the last values for a few failed polls, then give up and back off."""
        self.failed_polls += 1
        self.last_error = str(err)
        if self.data is not None and self.failed_polls < MAX_TOLERATED_FAILURES:
            _LOGGER.info(
                "%s: poll failed (%s of %s tolerated): %s",
                self.address,
                self.failed_polls,
                MAX_TOLERATED_FAILURES - 1,
                err,
            )
            return self.data
        if self.failed_polls >= MAX_TOLERATED_FAILURES:
            factor = min(self.failed_polls - MAX_TOLERATED_FAILURES + 2, 5)
            self.update_interval = timedelta(
                seconds=min(
                    self.base_interval * factor, max(self.base_interval, MAX_BACKOFF_INTERVAL)
                )
            )
        # Consecutive failures do not notify the entities by themselves.
        self.async_update_listeners()
        raise err

    async def async_write_setting(self, register: int, value: int) -> None:
        """Write one setting register and verify it by reading the settings back.

        Mirrors what the phone app does: read the settings block, write the
        register, read the settings block again. Raises UpdateFailed if the
        controller does not acknowledge the write or does not show the new value,
        and ValueError if the register or value is not allowed.
        """
        ble_device = self._require_device()
        frame = build_write_frame(register, value)  # validates register and range
        try:
            async with self._lock, self._async_session(ble_device) as session:
                await session.request(SETTINGS_REQUEST, SETTINGS_LENGTH, parse_settings)
                await session.request(
                    frame, ACK_LENGTH, lambda r: parse_write_ack(r, register)
                )
                for attempt in range(VERIFY_ATTEMPTS):
                    settings = await session.request(
                        SETTINGS_REQUEST, SETTINGS_LENGTH, parse_settings
                    )
                    if settings["_settings_raw"][register] == value:
                        break
                    if attempt < VERIFY_ATTEMPTS - 1:
                        await asyncio.sleep(VERIFY_DELAY)
                else:
                    raise ZhiJinError(
                        f"controller did not apply 0x{register:04X} = {value}"
                    )
        except COMMUNICATION_ERRORS as err:
            raise UpdateFailed(f"Error talking to {self.address}: {err}") from err

        data = dict(self.data or {})
        data.update(settings)
        self._record_success()
        self.async_set_updated_data(data)

    async def async_set_load(self, on: bool) -> None:
        """Switch the load output."""
        await self.async_write_setting(REG_LOAD, 1 if on else 0)
