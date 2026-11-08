"""Cramer Connect integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.ssl import get_default_context

from .api import CramerConnectAuthError, CramerConnectApiError, CramerConnectClient
from .const import CONF_PIN, DOMAIN
from .coordinator import CramerConnectCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.LAWN_MOWER,
    Platform.UPDATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = CramerConnectClient(session, ssl_context=get_default_context())

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    try:
        auth = await client.authenticate(username, password)
    except CramerConnectAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except CramerConnectApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = CramerConnectCoordinator(
        hass, client, auth, username, password, pin=entry.options.get(CONF_PIN)
    )
    await coordinator.async_config_entry_first_refresh()

    _async_remove_stale_entities(hass, coordinator)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _async_remove_stale_entities(
    hass: HomeAssistant, coordinator: CramerConnectCoordinator
) -> None:
    """Drop entities replaced in 0.7.0 (update binary sensor → update entity)."""
    registry = er.async_get(hass)
    for device_id in coordinator.data or {}:
        entity_id = registry.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{device_id}_update"
        )
        if entity_id:
            registry.async_remove(entity_id)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    coordinator: CramerConnectCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.pin = entry.options.get(CONF_PIN) or None


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
