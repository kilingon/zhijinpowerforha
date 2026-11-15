"""Bluetooth connection handling for the ZhiJinPower MPPT integration."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
import logging
from typing import Any, TypeVar

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from .protocol import (
    NOTIFY_CHAR_UUID,
    REQUEST,
    RESPONSE_LENGTH,
    WRITE_CHAR_UUID,
    parse_response,
)

_LOGGER = logging.getLogger(__name__)

RESPONSE_TIMEOUT = 4  # seconds to wait for one reply
REQUEST_ATTEMPTS = 3
CLOSE_TIMEOUT = 8  # seconds for stop_notify / disconnect each

_T = TypeVar("_T")


class ZhiJinError(Exception):
    """The controller did not answer as expected."""


# Everything that can go wrong while talking to the controller.
COMMUNICATION_ERRORS = (BleakError, TimeoutError, ZhiJinError)


class Session:
    """One connection: send a frame, collect the notification bytes, parse them."""

    def __init__(self, client: BleakClientWithServiceCache, address: str) -> None:
        self._client = client
        self._address = address
        self._buffer = bytearray()
        self._expected = 0
        self._event = asyncio.Event()

    def on_notify(self, _characteristic: Any, data: bytearray) -> None:
        """Collect notification bytes.

        A reply can arrive in one notification or in 20 byte chunks, depending on
        the negotiated MTU, so bytes are collected until the frame is complete.
        """
        self._buffer.extend(data)
        if len(self._buffer) >= self._expected:
            self._event.set()

    async def request(
        self, frame: bytes, length: int, parse: Callable[[bytes], _T]
    ) -> _T:
        """Write frame and return parse(reply). Retries on bad or missing replies."""
        last_error = "no response"
        for _ in range(REQUEST_ATTEMPTS):
            self._buffer.clear()
            self._event.clear()
            self._expected = length
            await self._client.write_gatt_char(WRITE_CHAR_UUID, frame, response=False)
            try:
                await asyncio.wait_for(self._event.wait(), timeout=RESPONSE_TIMEOUT)
                return parse(bytes(self._buffer))
            except TimeoutError:
                last_error = f"timeout, got {len(self._buffer)} bytes"
            except ValueError as err:
                last_error = str(err)
            _LOGGER.debug("%s: bad reply (%s), retrying", self._address, last_error)
        raise ZhiJinError(f"{self._address}: {last_error}")


@asynccontextmanager
async def async_open_session(
    ble_device: BLEDevice,
    name: str,
    ble_device_callback: Callable[[], BLEDevice | None] | None = None,
) -> AsyncIterator[Session]:
    """Connect, enable notifications and yield a Session. Disconnects on exit."""
    client = await establish_connection(
        BleakClientWithServiceCache,
        ble_device,
        name,
        max_attempts=3,
        ble_device_callback=ble_device_callback,
    )
    try:
        session = Session(client, ble_device.address)
        await client.start_notify(NOTIFY_CHAR_UUID, session.on_notify)
        yield session
    finally:
        await _async_close(client, ble_device.address)


async def _async_close(client: BleakClientWithServiceCache, address: str) -> None:
    """Always release the controller: it accepts a single connection and stops
    advertising while connected, so a connection left open locks everybody out.

    Runs shielded, so a cancelled poll cannot abort the disconnect half way, and
    with timeouts, so a hanging stop_notify cannot keep the link open.
    """

    async def _close() -> None:
        try:
            await asyncio.wait_for(client.stop_notify(NOTIFY_CHAR_UUID), CLOSE_TIMEOUT)
        except (BleakError, TimeoutError, KeyError, OSError):
            pass
        try:
            await asyncio.wait_for(client.disconnect(), CLOSE_TIMEOUT)
        except (BleakError, TimeoutError, OSError) as err:
            _LOGGER.warning("%s: could not disconnect cleanly: %s", address, err)

    await asyncio.shield(asyncio.ensure_future(_close()))


async def async_read_status(
    ble_device: BLEDevice,
    name: str,
    ble_device_callback: Callable[[], BLEDevice | None] | None = None,
) -> dict[str, Any]:
    """Connect once and read the status block. Used to test a controller."""
    async with async_open_session(ble_device, name, ble_device_callback) as session:
        return await session.request(REQUEST, RESPONSE_LENGTH, parse_response)
