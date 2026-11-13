"""Base entity for the ZhiJinPower MPPT integration."""
from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity, UpdateFailed

from .const import DOMAIN
from .coordinator import ZhiJinCoordinator


class ZhiJinEntity(CoordinatorEntity[ZhiJinCoordinator]):
    """Entity that reads one value from the coordinator data."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: ZhiJinCoordinator, description: EntityDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
            name=coordinator.config_entry.title,
            manufacturer="ZhiJinPower",
            model="MPPT solar charge controller",
        )

    async def _async_write(self, register: int, value: int) -> None:
        """Write a setting register, turning failures into Home Assistant errors."""
        try:
            await self.coordinator.async_write_setting(register, value)
        except (UpdateFailed, ValueError) as err:
            raise HomeAssistantError(f"Could not change the setting: {err}") from err
