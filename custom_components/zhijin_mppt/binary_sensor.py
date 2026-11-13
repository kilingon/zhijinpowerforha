"""Binary sensors for the ZhiJinPower MPPT integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
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
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    coordinator: ZhiJinCoordinator = entry.runtime_data
    async_add_entities(ZhiJinBinarySensor(coordinator, desc) for desc in BINARY_SENSORS)


class ZhiJinBinarySensor(ZhiJinEntity, BinarySensorEntity):
    """A boolean value from the controller."""

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get(self.entity_description.key)
