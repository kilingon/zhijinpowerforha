"""Battery type setting (select entity) for the ZhiJinPower MPPT integration."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ZhiJinEntity
from .protocol import BATTERY_TYPES, REG_BATTERY_TYPE

# Changing the battery type changes the charging profile of the controller, so
# this entity is disabled by default. Enable it deliberately in the entity settings.
BATTERY_TYPE_SELECT = SelectEntityDescription(
    key="battery_type",
    translation_key="battery_type",
    entity_category=EntityCategory.CONFIG,
    entity_registry_enabled_default=False,
    icon="mdi:car-battery",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the battery type select."""
    async_add_entities([ZhiJinBatteryTypeSelect(entry.runtime_data, BATTERY_TYPE_SELECT)])


class ZhiJinBatteryTypeSelect(ZhiJinEntity, SelectEntity):
    """Battery type: lithium, gel or lead-acid / LiFePO4 (names come from the translations)."""

    _attr_options = list(BATTERY_TYPES.values())

    @property
    def current_option(self) -> str | None:
        return BATTERY_TYPES.get(self.coordinator.data.get("battery_type"))

    async def async_select_option(self, option: str) -> None:
        for code, name in BATTERY_TYPES.items():
            if name == option:
                await self._async_write(REG_BATTERY_TYPE, code)
                return
