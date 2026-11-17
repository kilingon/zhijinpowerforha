"""Binary sensors for the ZhiJinPower MPPT integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ZhiJinCoordinator
from .entity import ZhiJinEntity

BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    # Actual state of the load output. It lags behind a switch command by several
    # seconds; the "Load" switch shows the commanded state instead.
    BinarySensorEntityDescription(
        key="load_on",
        translation_key="load_on",
        device_class=BinarySensorDeviceClass.POWER,
    ),
    BinarySensorEntityDescription(
        key="pv_day",
        translation_key="pv_day",
        device_class=BinarySensorDeviceClass.LIGHT,
    ),
    BinarySensorEntityDescription(
        key="wind_on",
        translation_key="wind_on",
        device_class=BinarySensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
    ),
)

CONNECTIVITY = BinarySensorEntityDescription(
    key="connectivity",
    translation_key="connectivity",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    coordinator: ZhiJinCoordinator = entry.runtime_data
    async_add_entities(ZhiJinBinarySensor(coordinator, desc) for desc in BINARY_SENSORS)
    async_add_entities([ZhiJinConnectivity(coordinator, CONNECTIVITY)])


class ZhiJinBinarySensor(ZhiJinEntity, BinarySensorEntity):
    """A boolean value from the controller."""

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get(self.entity_description.key)


class ZhiJinConnectivity(ZhiJinEntity, BinarySensorEntity):
    """On while the last poll worked. Always available, so it can report 'off'."""

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.last_update_success)
