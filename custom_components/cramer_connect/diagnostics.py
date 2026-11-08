"""Diagnostics download for Cramer Connect (tokens and location redacted)."""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_PIN, DOMAIN
from .coordinator import CramerConnectCoordinator

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_PIN,
    "latitude",
    "longitude",
    "mac",
    "sn",
    "serial_number",
    "mower_serial_number",
    "active_code",
    "authorize_code",
    "device_authorize",
    "access_key",
    "name",
}


def _decode_datapoints(datapoints: dict[str, Any]) -> dict[str, Any]:
    """Expand JSON-string datapoint values so nested fields can be redacted."""
    decoded: dict[str, Any] = {}
    for key, dp in datapoints.items():
        if isinstance(dp, dict) and isinstance(dp.get("value"), str):
            try:
                value = json.loads(dp["value"])
            except ValueError:
                value = dp["value"]
            decoded[key] = {**dp, "value": value}
        else:
            decoded[key] = dp
    return decoded


def device_diagnostics(device: Any) -> dict[str, Any]:
    data = asdict(device)
    data["datapoints"] = _decode_datapoints(data.get("datapoints") or {})
    data["state_label"] = device.state_label
    data["last_seen"] = device.last_seen.isoformat() if device.last_seen else None
    return async_redact_data(data, TO_REDACT)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: CramerConnectCoordinator = hass.data[DOMAIN][entry.entry_id]
    auth = coordinator.auth
    return {
        "entry": async_redact_data(
            {"data": dict(entry.data), "options": dict(entry.options)}, TO_REDACT
        ),
        "auth": {
            "is_fleet_user": auth.is_fleet_user,
            "has_mqtt_credentials": auth.has_mqtt_credentials,
            "expires_in": auth.expires_in,
            "fetched_at": auth.fetched_at.isoformat(),
        },
        "devices": [device_diagnostics(d) for d in (coordinator.data or {}).values()],
    }
