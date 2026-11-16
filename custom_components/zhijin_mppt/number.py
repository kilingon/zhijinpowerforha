"""Voltage settings (number entities) for the ZhiJinPower MPPT integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ZhiJinEntity
from .protocol import (
    REG_CUTOFF_VOLTAGE,
    REG_FLOAT_VOLTAGE,
    REG_RECOVERY_VOLTAGE,
    SYSTEM_VOLTAGES,
    VOLTAGE_WRITE_MODES,
    WRITABLE,
)


@dataclass(frozen=True, kw_only=True)
class ZhiJinNumberDescription(NumberEntityDescription):
    """Describes a voltage setting stored in one register (tenths of a volt)."""

    register: int


def _voltage(key: str, register: int) -> ZhiJinNumberDescription:
    low, high = WRITABLE[register]  # 12 V limits from the controller manual
    return ZhiJinNumberDescription(
        key=key,
        translation_key=key,
        register=register,
        device_class=NumberDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        native_min_value=low / 10,
        native_max_value=high / 10,
        native_step=0.1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    )


NUMBERS: tuple[ZhiJinNumberDescription, ...] = (
    _voltage("float_voltage", REG_FLOAT_VOLTAGE),
    _voltage("recovery_voltage", REG_RECOVERY_VOLTAGE),
    _voltage("cutoff_voltage", REG_CUTOFF_VOLTAGE),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number entities."""
    async_add_entities(ZhiJinNumber(entry.runtime_data, desc) for desc in NUMBERS)


class ZhiJinNumber(ZhiJinEntity, NumberEntity):
    """A voltage setting of the controller."""

    entity_description: ZhiJinNumberDescription

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get(self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        raw = round(value * 10)
        data = self.coordinator.data or {}
        key = self.entity_description.key
        mode = data.get("system_voltage")
        if mode not in VOLTAGE_WRITE_MODES:
            name = SYSTEM_VOLTAGES.get(mode, f"code {mode}")
            raise HomeAssistantError(
                f"The system voltage mode is '{name}'. The limits of this integration "
                "are for 12 V systems, so voltages are not written in that mode."
            )
        # The cut-off voltage has to stay below the recovery voltage.
        if key == "cutoff_voltage" and raw >= round(data.get("recovery_voltage", 99) * 10):
            raise HomeAssistantError(
                "The discharge cut-off voltage must be lower than the recovery voltage"
            )
        if key == "recovery_voltage" and raw <= round(data.get("cutoff_voltage", 0) * 10):
            raise HomeAssistantError(
                "The discharge recovery voltage must be higher than the cut-off voltage"
            )
        await self._async_write(self.entity_description.register, raw)
