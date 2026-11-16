"""Config flow for the ZhiJinPower MPPT integration."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .connection import COMMUNICATION_ERRORS, async_read_status
from .const import (
    ADAPTER_AUTO,
    CONF_ADAPTER,
    CONF_SCAN_INTERVAL,
    CONF_SKIP_TEST,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SERVICE_UUID_FF00,
)

_LOGGER = logging.getLogger(__name__)

_MAC_SEPARATED = re.compile(r"^([0-9A-F]{2}[:-]){5}[0-9A-F]{2}$")
_MAC_PLAIN = re.compile(r"^[0-9A-F]{12}$")
# These controllers advertise as "ZJBE-<MAC without separators>" (ZJBX / ZJBW too)
_DEVICE_NAME = re.compile(r"^ZJB[A-Z0-9]-([0-9A-F]{12})$")


def normalize_address(value: str) -> str | None:
    """Return the Bluetooth address as AA:BB:CC:DD:EE:FF, or None if it is not one.

    Accepts AA:BB:CC:DD:EE:FF, AA-BB-CC-DD-EE-FF, AABBCCDDEEFF in any case, and the
    advertised device name (ZJBE-AABBCCDDEEFF).
    """
    text = (value or "").strip().upper()
    if match := _DEVICE_NAME.match(text):
        text = match.group(1)
    if _MAC_SEPARATED.match(text):
        text = re.sub(r"[:-]", "", text)
    if _MAC_PLAIN.match(text):
        return ":".join(text[i : i + 2] for i in range(0, 12, 2))
    return None


def default_name(address: str) -> str:
    """Name used when the device name is not known (typed address)."""
    return f"ZJBE-{address.replace(':', '')}"


class ZhiJinConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a ZhiJinPower controller."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, str] = {}
        self._address: str | None = None
        self._name: str | None = None
        self._offer_skip = False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return ZhiJinOptionsFlow()

    # --- helpers ---------------------------------------------------------------

    def _async_discover(self) -> dict[str, str]:
        """Controllers Home Assistant currently sees and has not configured yet."""
        current_ids = self._async_current_ids()
        found: dict[str, str] = {}
        for info in async_discovered_service_info(self.hass, connectable=True):
            if info.address in current_ids:
                continue
            name = info.name or ""
            if name.upper().startswith("ZJB") or SERVICE_UUID_FF00 in info.service_uuids:
                found[info.address] = name or info.address
        return found

    async def _async_test(self, address: str) -> str | None:
        """Connect and read the controller. Returns an error key, or None if fine."""
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, address, connectable=True
        )
        if ble_device is None:
            return "not_in_range"
        try:
            await async_read_status(
                ble_device,
                self._name or default_name(address),
                lambda: bluetooth.async_ble_device_from_address(
                    self.hass, address, connectable=True
                ),
            )
        except COMMUNICATION_ERRORS as err:
            _LOGGER.debug("Connection test for %s failed: %s", address, err)
            return "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error while testing %s", address)
            return "unknown"
        return None

    async def _async_validate_or_create(
        self, address: str, name: str | None, skip_test: bool
    ) -> tuple[ConfigFlowResult | None, str | None]:
        """Create the entry, or return an error key if the controller is not usable."""
        await self.async_set_unique_id(address, raise_on_progress=False)
        self._abort_if_unique_id_configured()
        self._name = name
        if not skip_test:
            if error := await self._async_test(address):
                self._offer_skip = True  # let the user add it anyway next time
                return None, error
        return (
            self.async_create_entry(
                title=name or default_name(address), data={CONF_ADDRESS: address}
            ),
            None,
        )

    def _with_skip(self, fields: dict[Any, Any]) -> vol.Schema:
        """Schema with the optional "add anyway" checkbox once a test has failed."""
        if self._offer_skip:
            fields = {**fields, vol.Optional(CONF_SKIP_TEST, default=False): bool}
        return vol.Schema(fields)

    # --- Bluetooth discovery ----------------------------------------------------

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a controller found by Home Assistant's Bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._address = discovery_info.address
        self._name = discovery_info.name
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered controller (and test the connection)."""
        assert self._address is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            result, error = await self._async_validate_or_create(
                self._address, self._name, user_input.get(CONF_SKIP_TEST, False)
            )
            if result is not None:
                return result
            errors["base"] = error or "unknown"
        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=self._with_skip({}),
            errors=errors,
            description_placeholders={"name": self._name or self._address},
        )

    # --- manual setup -------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start: pick a discovered controller, or type the address."""
        self._discovered = self._async_discover()
        if not self._discovered:
            return await self.async_step_manual()
        return self.async_show_menu(
            step_id="user", menu_options=["pick_device", "manual"]
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose one of the controllers found by Bluetooth."""
        if not self._discovered:
            self._discovered = self._async_discover()
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            result, error = await self._async_validate_or_create(
                address,
                self._discovered.get(address),
                user_input.get(CONF_SKIP_TEST, False),
            )
            if result is not None:
                return result
            errors["base"] = error or "unknown"
        schema = self._with_skip(
            {
                vol.Required(CONF_ADDRESS): vol.In(
                    {
                        address: f"{name} ({address})"
                        for address, name in self._discovered.items()
                    }
                )
            }
        )
        return self.async_show_form(
            step_id="pick_device",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Type the Bluetooth address (MAC) of the controller."""
        errors: dict[str, str] = {}
        if user_input is not None:
            address = normalize_address(user_input[CONF_ADDRESS])
            if address is None:
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                result, error = await self._async_validate_or_create(
                    address, None, user_input.get(CONF_SKIP_TEST, False)
                )
                if result is not None:
                    return result
                errors["base"] = error or "unknown"
        schema = self._with_skip({vol.Required(CONF_ADDRESS): str})
        return self.async_show_form(
            step_id="manual",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )


class ZhiJinOptionsFlow(OptionsFlow):
    """Options: polling interval and which Bluetooth adapter / proxy to use."""

    def _adapter_options(self) -> list[SelectOptionDict]:
        options = [SelectOptionDict(value=ADAPTER_AUTO, label="Auto / Otomatik")]
        known = set()
        for scanner in bluetooth.async_current_scanners(self.hass):
            known.add(scanner.source)
            options.append(
                SelectOptionDict(
                    value=scanner.source, label=f"{scanner.name} ({scanner.source})"
                )
            )
        saved = self.config_entry.options.get(CONF_ADAPTER, ADAPTER_AUTO)
        if saved != ADAPTER_AUTO and saved not in known:
            options.append(SelectOptionDict(value=saved, label=f"{saved} (not connected)"))
        return options

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    CONF_ADAPTER: user_input.get(CONF_ADAPTER, ADAPTER_AUTO),
                }
            )
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        adapter = self.config_entry.options.get(CONF_ADAPTER, ADAPTER_AUTO)
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=MAX_SCAN_INTERVAL,
                        step=1,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(CONF_ADAPTER, default=adapter): SelectSelector(
                    SelectSelectorConfig(
                        options=self._adapter_options(),
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
