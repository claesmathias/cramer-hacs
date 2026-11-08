"""Config flow for Cramer Connect."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CramerAuth, CramerConnectAuthError, CramerConnectApiError, CramerConnectClient
from .const import CONF_ORGANIZATION_ID, CONF_PIN, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class CramerConnectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    _reauth_entry: config_entries.ConfigEntry | None = None

    async def _async_try_login(
        self, username: str, password: str, errors: dict[str, str]
    ) -> CramerAuth | None:
        client = CramerConnectClient(async_get_clientsession(self.hass))
        try:
            return await client.authenticate(username, password)
        except CramerConnectAuthError as err:
            _LOGGER.error("Authentication failed: %s", err)
            errors["base"] = "invalid_auth"
        except (CramerConnectApiError, aiohttp.ClientError) as err:
            _LOGGER.error("Cannot connect to Cramer API: %s", err)
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error during config flow")
            errors["base"] = "unknown"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            auth = await self._async_try_login(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD], errors
            )
            if auth is not None:
                await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_ORGANIZATION_ID: auth.organization_id,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        entry = self._reauth_entry
        assert entry is not None
        username = entry.data[CONF_USERNAME]

        if user_input is not None:
            auth = await self._async_try_login(
                username, user_input[CONF_PASSWORD], errors
            )
            if auth is not None:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"username": username},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> CramerConnectOptionsFlow:
        return CramerConnectOptionsFlow()


def valid_pin(value: str) -> bool:
    return value.isdigit() and len(value) <= 5 and int(value) <= 0xFFFF


class CramerConnectOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            pin = str(user_input.get(CONF_PIN) or "").strip()
            if pin and not valid_pin(pin):
                errors[CONF_PIN] = "invalid_pin"
            else:
                return self.async_create_entry(data={CONF_PIN: pin})

        current = self.config_entry.options.get(CONF_PIN, "")
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Optional(CONF_PIN, description={"suggested_value": current}): str}
            ),
            errors=errors,
        )
