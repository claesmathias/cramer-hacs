"""Lawn mower entity for Cramer Connect."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NONSTOP_MAX_DAYS, SCHEDULE_DAYS
from .coordinator import CramerConnectCoordinator
from .entity import CramerMowerEntity, CramerScheduleMixin, remotely_controllable

SERVICE_PARK = "park"
SERVICE_SET_SCHEDULE = "set_schedule"
SERVICE_START_NONSTOP = "start_nonstop_mowing"
SERVICE_CANCEL_NONSTOP = "cancel_nonstop_mowing"
SERVICE_SET_CLOCK = "set_clock"
ATTR_DURATION = "duration"
ATTR_DAYS = "days"

_RETURNING = getattr(LawnMowerActivity, "RETURNING", LawnMowerActivity.MOWING)

# DeviceBean.state → LawnMowerActivity
STATE_TO_ACTIVITY = {
    "0": LawnMowerActivity.DOCKED,  # starting up
    "1": LawnMowerActivity.PAUSED,  # stop button pressed
    "2": LawnMowerActivity.DOCKED,  # parked
    "3": LawnMowerActivity.PAUSED,
    "4": LawnMowerActivity.MOWING,
    "5": LawnMowerActivity.MOWING,  # leaving charging station
    "6": _RETURNING,  # searching charging station
    "7": LawnMowerActivity.DOCKED,  # charging
    "8": LawnMowerActivity.ERROR,
    "9": LawnMowerActivity.ERROR,
    "10": LawnMowerActivity.ERROR,  # recovery
    "11": LawnMowerActivity.ERROR,  # alarm
    "12": LawnMowerActivity.MOWING,  # secondary area
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CramerConnectCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        CramerLawnMower(coordinator, device_id)
        for device_id, device in coordinator.data.items()
        if remotely_controllable(device)
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_PARK,
        {
            vol.Optional(ATTR_DURATION): vol.All(
                cv.positive_int, vol.Range(min=1, max=65533)
            )
        },
        "async_park_service",
    )
    platform.async_register_entity_service(
        SERVICE_SET_SCHEDULE,
        {
            vol.Required(ATTR_DAYS): vol.All(cv.ensure_list, [vol.In(SCHEDULE_DAYS)]),
            vol.Optional("timer_1_start"): cv.time,
            vol.Optional("timer_1_end"): cv.time,
            vol.Optional("timer_2_start"): cv.time,
            vol.Optional("timer_2_end"): cv.time,
        },
        "async_set_schedule",
    )
    platform.async_register_entity_service(
        SERVICE_START_NONSTOP,
        {
            vol.Required(ATTR_DAYS): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=NONSTOP_MAX_DAYS)
            )
        },
        "async_start_nonstop_mowing",
    )
    platform.async_register_entity_service(
        SERVICE_CANCEL_NONSTOP, {}, "async_cancel_nonstop_mowing"
    )
    platform.async_register_entity_service(SERVICE_SET_CLOCK, {}, "async_set_clock")


class CramerLawnMower(CramerScheduleMixin, CramerMowerEntity, LawnMowerEntity):
    _attr_name = None
    _attr_supported_features = (
        LawnMowerEntityFeature.START_MOWING
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.DOCK
    )

    def __init__(self, coordinator: CramerConnectCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_lawn_mower"

    @property
    def activity(self) -> LawnMowerActivity | None:
        return STATE_TO_ACTIVITY.get(self._device.state or "")

    @property
    def extra_state_attributes(self) -> dict:
        device = self._device
        return {
            "state": device.state_label,
            "reason": device.next_start_reason,
            "battery": device.battery,
            "nonstop_mowing": device.nonstop_mowing,
        }

    async def async_start_mowing(self) -> None:
        await self.async_start()

    async def async_pause(self) -> None:
        await self.async_stop()

    async def async_dock(self) -> None:
        await self.async_park(None)

    async def async_park_service(self, duration: int | None = None) -> None:
        await self.async_park(duration)
