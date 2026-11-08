"""Button entities for remote control of Cramer mowers (RLM1, via MQTT)."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import CramerConnectCoordinator
from .entity import CramerMowerEntity, CramerScheduleMixin, remotely_controllable


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CramerConnectCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ButtonEntity] = []
    for device_id, device in coordinator.data.items():
        if not remotely_controllable(device):
            continue
        entities.extend([
            CramerStartButton(coordinator, device_id),
            CramerPauseButton(coordinator, device_id),
            CramerStopButton(coordinator, device_id),
            CramerParkButton(coordinator, device_id),
            CramerSetClockButton(coordinator, device_id),
        ])
    async_add_entities(entities)


def minutes_until_end_of_day() -> int:
    """Same as StringUtils.remainMinute() in the app."""
    now = dt_util.now()
    end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    return max(1, int((end - now).total_seconds() // 60))


class _CramerMowerButton(CramerMowerEntity, ButtonEntity):
    _key: str

    def __init__(self, coordinator: CramerConnectCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_{self._key}"


class CramerStartButton(_CramerMowerButton):
    """Start mowing / resume schedule."""

    _key = "start"
    _attr_translation_key = "start"
    # Same as lawn_mower start — off by default to avoid duplicate controls
    _attr_entity_registry_enabled_default = False

    async def async_press(self) -> None:
        await self.async_start()


class CramerPauseButton(_CramerMowerButton):
    """Stop the mower where it is."""

    _key = "pause"
    _attr_translation_key = "pause"
    _attr_entity_registry_enabled_default = False

    async def async_press(self) -> None:
        await self.async_stop()


class CramerStopButton(_CramerMowerButton):
    """Send the mower home and park it until further notice."""

    _key = "stop"
    _attr_translation_key = "park_until_further_notice"

    async def async_press(self) -> None:
        await self.async_park(None)


class CramerParkButton(_CramerMowerButton):
    """Send the mower home and park it for the rest of the day."""

    _key = "park"
    _attr_translation_key = "park_rest_of_day"

    async def async_press(self) -> None:
        await self.async_park(minutes_until_end_of_day())


class CramerSetClockButton(CramerScheduleMixin, _CramerMowerButton):
    """Set the mower clock to Home Assistant's time (app: 'incorrect time')."""

    _key = "set_clock"
    _attr_translation_key = "set_clock"
    _attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        await self.async_set_clock()
