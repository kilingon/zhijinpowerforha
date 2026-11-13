"""Fixtures: a fake controller and a fake Bluetooth stack."""
from __future__ import annotations

from unittest.mock import patch

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from habluetooth import BluetoothServiceInfoBleak
import pytest

from custom_components.zhijin_mppt.const import SERVICE_UUID_FF00

from .fake_device import ADDRESS, NAME, FakeClient, FakeController

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow the custom integration in every test."""
    return


def make_service_info(
    name: str = NAME, address: str = ADDRESS, uuids: list[str] | None = None
) -> BluetoothServiceInfoBleak:
    """An advertisement like the one the controller sends."""
    uuids = [SERVICE_UUID_FF00] if uuids is None else uuids
    device = BLEDevice(address, name, {})
    advertisement = AdvertisementData(
        local_name=name,
        manufacturer_data={},
        service_data={},
        service_uuids=uuids,
        rssi=-60,
        tx_power=None,
        platform_data=(),
    )
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=uuids,
        source="local",
        device=device,
        advertisement=advertisement,
        connectable=True,
        time=0.0,
        tx_power=None,
    )


@pytest.fixture
def controller() -> FakeController:
    return FakeController()


class Radio:
    """Controls what the fake Bluetooth stack can see."""

    def __init__(self) -> None:
        self.in_range = True
        self.discovered: list[BluetoothServiceInfoBleak] = []


@pytest.fixture
def radio(mock_bluetooth, controller):
    """Patch Bluetooth so that the integration talks to the fake controller."""
    state = Radio()
    ble_device = BLEDevice(ADDRESS, NAME, {})

    async def fake_establish(client_class, device, name, **kwargs):
        return FakeClient(controller)

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            side_effect=lambda hass, address, connectable=True: ble_device
            if state.in_range
            else None,
        ),
        patch(
            "custom_components.zhijin_mppt.config_flow.async_discovered_service_info",
            side_effect=lambda hass, connectable=True: list(state.discovered),
        ),
        patch("custom_components.zhijin_mppt.connection.establish_connection", fake_establish),
        patch("custom_components.zhijin_mppt.connection.RESPONSE_TIMEOUT", 0.2),
        patch("custom_components.zhijin_mppt.coordinator.VERIFY_DELAY", 0.01),
    ):
        yield state
