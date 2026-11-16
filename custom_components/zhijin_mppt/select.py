"""Battery type setting (select entity) for the ZhiJinPower MPPT integration."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ZhiJinEntity
from .protocol import (
    BATTERY_TYPES,
    LOAD_MODES,
    REG_BATTERY_TYPE,
    REG_LOAD_MODE,
    REG_SYSTEM_VOLTAGE,
    SYSTEM_VOLTAGES,
    WRITABLE_SYSTEM_VOLTAGES,
)

# Changing the battery type changes the charging profile of the controller, so
# this entity is disabled by default. Enable it deliberately in the entity settings.
BATTERY_TYPE_SELECT = SelectEntityDescription(
    key="battery_type",
    translation_key="battery_type",
    entity_category=EntityCategory.CONFIG,
    entity_registry_enabled_default=False,
    icon="mdi:car-battery",
)

# Changing the load mode changes when the load output is switched, so this is
# disabled by default too. The write has not been verified on hardware.
LOAD_MODE_SELECT = SelectEntityDescription(
    key="load_mode_select",
    translation_key="load_mode_select",
    entity_category=EntityCategory.CONFIG,
    entity_registry_enabled_default=False,
    icon="mdi:cog",
)

# The system voltage mode scales the charging and cut-off voltages of the controller,
# so a wrong value can over-charge or over-discharge the battery. Disabled by default,
# and only Auto and 12 V can be chosen (the other values were never captured).
SYSTEM_VOLTAGE_SELECT = SelectEntityDescription(
    key="system_voltage_select",
    translation_key="system_voltage_select",
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
    coordinator = entry.runtime_data
    async_add_entities(
        [
            ZhiJinBatteryTypeSelect(coordinator, BATTERY_TYPE_SELECT),
            ZhiJinLoadModeSelect(coordinator, LOAD_MODE_SELECT),
            ZhiJinSystemVoltageSelect(coordinator, SYSTEM_VOLTAGE_SELECT),
        ]
    )


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


class ZhiJinLoadModeSelect(ZhiJinEntity, SelectEntity):
    """Load mode (menu 5): manual (Cot), auto, timer or output."""

    _attr_options = list(LOAD_MODES.values())

    @property
    def current_option(self) -> str | None:
        return LOAD_MODES.get(self.coordinator.data.get("load_mode"))

    async def async_select_option(self, option: str) -> None:
        for code, name in LOAD_MODES.items():
            if name == option:
                await self._async_write(REG_LOAD_MODE, code)
                return


class ZhiJinSystemVoltageSelect(ZhiJinEntity, SelectEntity):
    """System voltage mode: Auto or 12 V."""

    _attr_options = [SYSTEM_VOLTAGES[code] for code in WRITABLE_SYSTEM_VOLTAGES]

    @property
    def current_option(self) -> str | None:
        name = SYSTEM_VOLTAGES.get(self.coordinator.data.get("system_voltage"))
        return name if name in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        for code in WRITABLE_SYSTEM_VOLTAGES:
            if SYSTEM_VOLTAGES[code] == option:
                await self._async_write(REG_SYSTEM_VOLTAGE, code)
                return
