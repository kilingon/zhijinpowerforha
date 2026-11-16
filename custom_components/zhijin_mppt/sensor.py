"""Sensors for the ZhiJinPower MPPT integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ZhiJinCoordinator
from .entity import ZhiJinEntity
from .protocol import BATTERY_TYPES, LOAD_MODES, PV_STATES, SYSTEM_VOLTAGES


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
    SensorEntityDescription(
        key="system_voltage_name",
        translation_key="system_voltage_name",
        device_class=SensorDeviceClass.ENUM,
        options=list(SYSTEM_VOLTAGES.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:car-battery",
    ),
    SensorEntityDescription(
        key="pv_state",
        translation_key="pv_state",
        device_class=SensorDeviceClass.ENUM,
        options=list(PV_STATES.values()),
        icon="mdi:weather-sunny",
    ),
    # Raw registers whose meaning is not known (yet). Disabled by default, enable
    # them to watch how they change.
    _diagnostic("load_mode"),
    _diagnostic("setting_1002"),
    _diagnostic("setting_1003"),
    _diagnostic("register_1"),
    _diagnostic("register_6"),
    _diagnostic("register_8"),
)


# Connection diagnostics. They stay available when the controller cannot be reached,
# that is when they are most useful. Values come from the coordinator, not the controller.
CONNECTION_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="last_update",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="failed_polls",
        translation_key="failed_polls",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alert-circle-outline",
    ),
    SensorEntityDescription(
        key="last_error",
        translation_key="last_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:message-alert-outline",
    ),
    SensorEntityDescription(
        key="bluetooth_source",
        translation_key="bluetooth_source",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:bluetooth-connect",
    ),
    SensorEntityDescription(
        key="signal_strength",
        translation_key="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

_CONNECTION_ATTRIBUTES = {
    "last_update": "last_success",
    "failed_polls": "failed_polls",
    "last_error": "last_error",
    "bluetooth_source": "bluetooth_source",
    "signal_strength": "signal_strength",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator: ZhiJinCoordinator = entry.runtime_data
    async_add_entities(ZhiJinSensor(coordinator, desc) for desc in SENSORS)
    async_add_entities(
        ZhiJinConnectionSensor(coordinator, desc) for desc in CONNECTION_SENSORS
    )


class ZhiJinSensor(ZhiJinEntity, SensorEntity):
    """A value from the controller."""

    @property
    def native_value(self) -> float | int | str | None:
        return self.coordinator.data.get(self.entity_description.key)


class ZhiJinConnectionSensor(ZhiJinEntity, SensorEntity):
    """How the connection to the controller is doing. Always available."""

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> Any:
        return getattr(
            self.coordinator, _CONNECTION_ATTRIBUTES[self.entity_description.key]
        )
