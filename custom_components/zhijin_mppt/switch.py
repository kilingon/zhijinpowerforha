"""Load output switch for the ZhiJinPower MPPT integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ZhiJinEntity
from .protocol import REG_LOAD

LOAD_SWITCH = SwitchEntityDescription(
    key="load_switch",
    translation_key="load_switch",
    device_class=SwitchDeviceClass.SWITCH,
    icon="mdi:power-socket",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the load switch."""
    async_add_entities([ZhiJinLoadSwitch(entry.runtime_data, LOAD_SWITCH)])


class ZhiJinLoadSwitch(ZhiJinEntity, SwitchEntity):
    """Switches the load (output) terminals of the controller.

    The state comes from the settings block, which changes right after the
    command. The "Load output" binary sensor shows the actual output state from
    the status block, which can lag behind by several seconds.
    """

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get("load_setting")

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_write(REG_LOAD, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_write(REG_LOAD, 0)
