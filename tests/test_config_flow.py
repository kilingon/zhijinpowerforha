"""Config flow tests: discovery, typing the address, test connection, options."""
from datetime import timedelta
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResultType

from custom_components.zhijin_mppt.const import (
    CONF_ADAPTER,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    CONF_SKIP_TEST,
    DOMAIN,
)

from .conftest import make_service_info
from .fake_device import ADDRESS, NAME


@pytest.fixture
def mock_setup_entry():
    with patch("custom_components.zhijin_mppt.async_setup_entry", return_value=True) as mock:
        yield mock


async def _start_user_flow(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_discovered_controller_can_be_picked(hass, radio, mock_setup_entry):
    radio.discovered = [make_service_info()]
    result = await _start_user_flow(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["pick_device", "manual"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "pick_device"}
    )
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "pick_device"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {CONF_ADDRESS: ADDRESS}
    assert result["result"].unique_id == ADDRESS


async def test_other_devices_are_not_offered(hass, radio):
    radio.discovered = [
        make_service_info(name="SomeSpeaker", address="11:22:33:44:55:66", uuids=[]),
        make_service_info(),
    ]
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "pick_device"}
    )
    schema = result["data_schema"].schema
    options = next(iter(schema.values())).container
    assert list(options) == [ADDRESS]


async def test_menu_offers_typing_the_address(hass, radio, mock_setup_entry):
    radio.discovered = [make_service_info()]
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "manual"


async def test_nothing_discovered_asks_for_the_address(hass, radio, mock_setup_entry):
    result = await _start_user_flow(hass)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: "aa-bb-cc-dd-ee-ff"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ADDRESS: ADDRESS}
    assert result["title"] == NAME  # built from the address


async def test_manual_accepts_the_advertised_name(hass, radio, mock_setup_entry):
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: NAME}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ADDRESS: ADDRESS}


async def test_manual_rejects_a_bad_address(hass, radio, mock_setup_entry):
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: "not an address"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ADDRESS: "invalid_address"}
    # a bad address is a typo, not a failed connection: no "add anyway" option
    assert CONF_SKIP_TEST not in [str(k) for k in result["data_schema"].schema]


async def test_not_in_range_can_be_added_anyway(hass, radio, mock_setup_entry):
    radio.in_range = False
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_in_range"}
    assert CONF_SKIP_TEST in [str(k) for k in result["data_schema"].schema]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS, CONF_SKIP_TEST: True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ADDRESS: ADDRESS}


async def test_controller_that_does_not_answer(hass, radio, controller, mock_setup_entry):
    controller.silent = True
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # the controller wakes up: same form, second try works
    controller.silent = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_unexpected_error_is_reported(hass, radio, mock_setup_entry):
    with patch(
        "custom_components.zhijin_mppt.config_flow.async_read_status",
        side_effect=RuntimeError("boom"),
    ):
        result = await _start_user_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: ADDRESS}
        )
    assert result["errors"] == {"base": "unknown"}


async def test_bluetooth_discovery(hass, radio, mock_setup_entry):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=make_service_info(),
    )
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "bluetooth_confirm"
    assert result["description_placeholders"] == {"name": NAME}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {CONF_ADDRESS: ADDRESS}


async def test_bluetooth_discovery_connection_failure_can_be_skipped(
    hass, radio, controller, mock_setup_entry
):
    controller.silent = True
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=make_service_info(),
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "cannot_connect"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SKIP_TEST: True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_already_configured_controller_is_not_added_twice(hass, radio, mock_setup_entry):
    MockConfigEntry(
        domain=DOMAIN, data={CONF_ADDRESS: ADDRESS}, unique_id=ADDRESS, title=NAME
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=make_service_info(),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    result = await _start_user_flow(hass)  # nothing new to pick: straight to typing
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_configured_controller_is_not_offered_again(hass, radio):
    MockConfigEntry(
        domain=DOMAIN, data={CONF_ADDRESS: ADDRESS}, unique_id=ADDRESS, title=NAME
    ).add_to_hass(hass)
    radio.discovered = [make_service_info()]
    result = await _start_user_flow(hass)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "manual"


async def test_options_flow_changes_the_polling_interval(hass, radio):
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_ADDRESS: ADDRESS}, unique_id=ADDRESS, title=NAME
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.update_interval == timedelta(seconds=DEFAULT_SCAN_INTERVAL)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 90}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert entry.options == {CONF_SCAN_INTERVAL: 90, CONF_ADAPTER: "auto"}
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.update_interval == timedelta(seconds=90)


async def test_options_flow_offers_the_known_adapters_and_saves_the_choice(hass, radio):
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_ADDRESS: ADDRESS}, unique_id=ADDRESS, title=NAME
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    schema = result["data_schema"].schema
    selector = next(v for k, v in schema.items() if k == CONF_ADAPTER)
    values = [option["value"] for option in selector.config["options"]]
    assert values == ["auto", "local", "proxy"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 60, CONF_ADAPTER: "local"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_ADAPTER] == "local"
    assert entry.runtime_data.preferred_source == "local"
