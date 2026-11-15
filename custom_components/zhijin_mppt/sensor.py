"""Sensors for the ZhiJinPower MPPT integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ZhiJinCoordinator
from .entity import ZhiJinEntity
from .protocol import BATTERY_TYPES, LOAD_MODES


def _diagnostic(key: str, *, enabled: bool = False) -> SensorEntityDescription:
    """A raw register value, disabled by default."""
    return SensorEntityDescription(
        key=key,
        translation_key=key,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=enabled,
    )


SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="charge_current",
        translation_key="charge_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="load_current",
        translation_key="load_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="total_generation",
        translation_key="total_generation",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="Ah",
        suggested_display_precision=1,
        icon="mdi:solar-power",
    ),
    SensorEntityDescription(
        key="charge_stage",
        translation_key="charge_stage",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:battery-charging",
    ),
    SensorEntityDescription(
        key="battery_type_name",
        translation_key="battery_type_name",
        device_class=SensorDeviceClass.ENUM,
        options=list(BATTERY_TYPES.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:car-battery",
    ),
    SensorEntityDescription(
        key="load_mode_name",
        translation_key="load_mode_name",
        device_class=SensorDeviceClass.ENUM,
        options=list(LOAD_MODES.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:cog",
    ),
    # Raw registers whose meaning is not known (yet). Disabled by default, enable
    # them to watch how they change.
    _diagnostic("load_mode"),
    _diagnostic("setting_1002"),
    _diagnostic("setting_1003"),
    _diagnostic("setting_1008"),
    _diagnostic("register_1"),
    _diagnostic("register_6"),
    _diagnostic("register_8"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator: ZhiJinCoordinator = entry.runtime_data
    async_add_entities(ZhiJinSensor(coordinator, desc) for desc in SENSORS)


class ZhiJinSensor(ZhiJinEntity, SensorEntity):
    """A value from the controller."""

    @property
    def native_value(self) -> float | int | str | None:
        return self.coordinator.data.get(self.entity_description.key)
