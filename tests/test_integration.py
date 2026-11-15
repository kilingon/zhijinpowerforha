"""Integration tests: set up the entry against a fake controller and use the entities."""
import asyncio
from datetime import timedelta
import json

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.zhijin_mppt.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from custom_components.zhijin_mppt.diagnostics import async_get_config_entry_diagnostics

from .fake_device import ADDRESS, NAME


async def setup_entry(hass) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_ADDRESS: ADDRESS}, unique_id=ADDRESS, title=NAME
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def eid(hass, platform: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{ADDRESS}_{key}")
    assert entity_id is not None, f"no {platform} entity for {key}"
    return entity_id


def state(hass, platform: str, key: str):
    return hass.states.get(eid(hass, platform, key))


async def call(hass, domain: str, service: str, platform: str, key: str, **data):
    await hass.services.async_call(
        domain, service, {"entity_id": eid(hass, platform, key), **data}, blocking=True
    )


async def poll(hass, seconds: int = DEFAULT_SCAN_INTERVAL + 1) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()
    # the fake radio answers from the event loop; give the poll time to finish
    for _ in range(20):
        await asyncio.sleep(0.05)
        await hass.async_block_till_done()


async def test_values_are_shown(hass, radio, controller):
    entry = await setup_entry(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert controller.log[:2] == ["status", "settings"]

    assert state(hass, "sensor", "battery_voltage").state == "12.4"
    assert state(hass, "sensor", "load_current").state == "0.1"
    assert state(hass, "sensor", "charge_current").state == "0.0"
    assert state(hass, "sensor", "temperature").state == "20.6"
    assert state(hass, "sensor", "total_generation").state == "798.7"
    assert state(hass, "sensor", "battery_type_name").state == "gel"
    assert state(hass, "sensor", "load_mode_name").state == "manual"
    assert state(hass, "number", "float_voltage").state == "14.5"
    assert state(hass, "number", "recovery_voltage").state == "12.6"
    assert state(hass, "number", "cutoff_voltage").state == "10.8"
    assert state(hass, "switch", "load_switch").state == STATE_ON
    assert state(hass, "binary_sensor", "load_on").state == STATE_ON


async def test_entity_names_come_from_the_translations(hass, radio):
    await setup_entry(hass)
    assert state(hass, "sensor", "battery_voltage").attributes["friendly_name"] == f"{NAME} Battery voltage"
    assert state(hass, "switch", "load_switch").attributes["friendly_name"] == f"{NAME} Load"
    assert state(hass, "number", "cutoff_voltage").attributes["friendly_name"] == f"{NAME} Discharge cut-off voltage"


async def test_device_registry(hass, radio):
    await setup_entry(hass)
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, ADDRESS)})
    assert device is not None
    assert device.name == NAME and device.manufacturer == "ZhiJinPower"
    assert (dr.CONNECTION_BLUETOOTH, ADDRESS) in device.connections


async def test_raw_registers_and_battery_type_select_are_disabled_by_default(hass, radio):
    await setup_entry(hass)
    registry = er.async_get(hass)
    for platform, key in [
        ("sensor", "register_1"), ("sensor", "register_6"), ("sensor", "register_8"),
        ("sensor", "setting_1002"), ("sensor", "setting_1003"), ("sensor", "setting_1008"),
        ("sensor", "load_mode"), ("select", "battery_type"), ("select", "load_mode_select"),
    ]:
        entry = registry.async_get(eid(hass, platform, key))
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION, key
        assert hass.states.get(entry.entity_id) is None


async def test_replies_in_20_byte_chunks_work(hass, radio, controller):
    controller.split = True
    await setup_entry(hass)
    assert state(hass, "sensor", "battery_voltage").state == "12.4"
    assert state(hass, "number", "recovery_voltage").state == "12.6"


async def test_load_switch_uses_the_commanded_state(hass, radio, controller):
    await setup_entry(hass)
    controller.log.clear()
    await call(hass, "switch", "turn_off", "switch", "load_switch")
    # like the phone app: read settings, write, read settings again
    assert controller.log == ["settings", "write 1007=0", "settings"]
    assert controller.reg[0x1007] == 0
    assert state(hass, "switch", "load_switch").state == STATE_OFF
    # the status block still shows the old output state for a while ...
    assert state(hass, "binary_sensor", "load_on").state == STATE_ON
    # ... and catches up on a later poll
    controller.status[6] = 0
    controller.log.clear()
    await poll(hass)
    assert state(hass, "binary_sensor", "load_on").state == STATE_OFF
    assert state(hass, "switch", "load_switch").state == STATE_OFF

    await call(hass, "switch", "turn_on", "switch", "load_switch")
    assert controller.reg[0x1007] == 1
    assert state(hass, "switch", "load_switch").state == STATE_ON


async def test_voltage_settings_can_be_changed(hass, radio, controller):
    await setup_entry(hass)
    await call(hass, "number", "set_value", "number", "float_voltage", value=14.4)
    await call(hass, "number", "set_value", "number", "recovery_voltage", value=12.7)
    await call(hass, "number", "set_value", "number", "cutoff_voltage", value=10.9)
    assert (controller.reg[0x1004], controller.reg[0x1009], controller.reg[0x1006]) == (144, 127, 109)
    assert state(hass, "number", "float_voltage").state == "14.4"
    assert state(hass, "number", "recovery_voltage").state == "12.7"
    assert state(hass, "number", "cutoff_voltage").state == "10.9"
    # nothing else was touched
    assert controller.reg[0x1001] == 2 and controller.reg[0x1007] == 1 and controller.reg[0x1005] == 0


async def test_number_limits_come_from_the_manual(hass, radio):
    await setup_entry(hass)
    for key, low, high in [
        ("float_voltage", 12.0, 14.5), ("recovery_voltage", 11.0, 13.0), ("cutoff_voltage", 9.0, 11.5),
    ]:
        attributes = state(hass, "number", key).attributes
        assert (attributes["min"], attributes["max"], attributes["step"]) == (low, high, 0.1)


async def test_out_of_range_and_inconsistent_values_never_reach_the_controller(hass, radio, controller):
    await setup_entry(hass)
    controller.log.clear()
    for key, value in [
        ("float_voltage", 15.0),  # above the manual limit
        ("cutoff_voltage", 12.8),  # would be above the recovery voltage (12.6)
        ("recovery_voltage", 10.5),  # would be below the cut-off voltage (10.8)
    ]:
        with pytest.raises(HomeAssistantError):
            await call(hass, "number", "set_value", "number", key, value=value)
    assert controller.log == []


async def test_failed_write_is_reported_and_state_is_kept(hass, radio, controller):
    await setup_entry(hass)
    controller.apply_writes = False
    with pytest.raises(HomeAssistantError, match="did not apply"):
        await call(hass, "switch", "turn_off", "switch", "load_switch")
    assert state(hass, "switch", "load_switch").state == STATE_ON
    controller.apply_writes = True
    await call(hass, "switch", "turn_off", "switch", "load_switch")
    assert state(hass, "switch", "load_switch").state == STATE_OFF


async def test_battery_type_select(hass, radio, controller):
    entry = await setup_entry(hass)
    er.async_get(hass).async_update_entity(eid(hass, "select", "battery_type"), disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    select = state(hass, "select", "battery_type")
    assert select.state == "gel"
    assert select.attributes["options"] == ["lithium", "gel", "lead_acid"]
    await call(hass, "select", "select_option", "select", "battery_type", option="lead_acid")
    assert controller.reg[0x1001] == 3
    assert state(hass, "select", "battery_type").state == "lead_acid"
    assert state(hass, "sensor", "battery_type_name").state == "lead_acid"


async def test_not_in_range_at_startup_retries_later(hass, radio):
    radio.in_range = False
    entry = await setup_entry(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_entities_become_unavailable_and_recover(hass, radio, controller):
    await setup_entry(hass)
    controller.silent = True
    await poll(hass)
    assert state(hass, "sensor", "battery_voltage").state == STATE_UNAVAILABLE
    assert state(hass, "switch", "load_switch").state == STATE_UNAVAILABLE

    controller.silent = False
    controller.status[1] = 130
    await poll(hass, seconds=2 * DEFAULT_SCAN_INTERVAL + 10)
    assert state(hass, "sensor", "battery_voltage").state == "13.0"


async def test_unload(hass, radio):
    entry = await setup_entry(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert state(hass, "sensor", "battery_voltage").state == STATE_UNAVAILABLE


async def test_diagnostics_do_not_contain_the_address(hass, radio):
    entry = await setup_entry(hass)
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["data"]["battery_voltage"] == 12.4
    assert diagnostics["entry"]["data"][CONF_ADDRESS] == "**REDACTED**"
    assert diagnostics["entry"]["title"] == "**REDACTED**"
    dump = json.dumps(diagnostics, default=str)
    assert ADDRESS not in dump and ADDRESS.replace(":", "") not in dump


async def test_load_mode_is_read_from_0x1005(hass, radio, controller):
    controller.reg[0x1005] = 3
    await setup_entry(hass)
    assert state(hass, "sensor", "load_mode_name").state == "output"


async def test_load_switch_refuses_when_not_in_manual_mode(hass, radio, controller):
    controller.reg[0x1005] = 1  # auto
    await setup_entry(hass)
    controller.log.clear()
    with pytest.raises(HomeAssistantError, match="not manual"):
        await call(hass, "switch", "turn_off", "switch", "load_switch")
    assert controller.log == []


async def test_load_mode_select(hass, radio, controller):
    entry = await setup_entry(hass)
    er.async_get(hass).async_update_entity(eid(hass, "select", "load_mode_select"), disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    select = state(hass, "select", "load_mode_select")
    assert select.state == "manual"
    assert select.attributes["options"] == ["manual", "auto", "timer", "output"]
    await call(hass, "select", "select_option", "select", "load_mode_select", option="timer")
    assert controller.reg[0x1005] == 2
    assert state(hass, "select", "load_mode_select").state == "timer"
    # the switch is locked now, the mode can be put back
    with pytest.raises(HomeAssistantError, match="not manual"):
        await call(hass, "switch", "turn_on", "switch", "load_switch")
    await call(hass, "select", "select_option", "select", "load_mode_select", option="manual")
    assert controller.reg[0x1005] == 0
