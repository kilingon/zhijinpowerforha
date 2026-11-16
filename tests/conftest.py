"""Fixtures: a fake controller and a fake Bluetooth stack."""
from __future__ import annotations

from types import SimpleNamespace
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
        # scanners (adapters / proxies) that currently hear the controller, with RSSI
        self.hearing: dict[str, int] = {"local": -61}
        # every scanner Home Assistant knows, with its display name
        self.scanners: dict[str, str] = {"local": "Local adapter", "proxy": "Proxy"}

    def best(self) -> tuple[str, int] | None:
        if not self.in_range or not self.hearing:
            return None
        return max(self.hearing.items(), key=lambda item: item[1])


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
            "homeassistant.components.bluetooth.async_scanner_devices_by_address",
            side_effect=lambda hass, address, connectable=True: [
                SimpleNamespace(
                    scanner=SimpleNamespace(source=source, name=state.scanners.get(source, source)),
                    ble_device=ble_device,
                    advertisement=SimpleNamespace(rssi=rssi),
                )
                for source, rssi in state.hearing.items()
                if state.in_range
            ],
        ),
        patch(
            "homeassistant.components.bluetooth.async_last_service_info",
            side_effect=lambda hass, address, connectable=True: SimpleNamespace(
                source=state.best()[0], rssi=state.best()[1]
            )
            if state.best()
            else None,
        ),
        patch(
            "homeassistant.components.bluetooth.async_current_scanners",
            side_effect=lambda hass: [
                SimpleNamespace(source=source, name=name)
                for source, name in state.scanners.items()
            ],
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
