"""Button entities for remote control of Cramer mowers."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import CramerDevice, CramerConnectTokenExpiredError
from .const import DOMAIN
from .coordinator import CramerConnectCoordinator

_LOGGER = logging.getLogger(__name__)

# SignalR hub method names (confirmed from APK classes2.dex)
_CMD_START = "StartMowerRequest"
_CMD_STOP = "ParkMowerRequest"
_CMD_PARK = "PauseMowerRequest"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CramerConnectCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ButtonEntity] = []
    for device_id, device in coordinator.data.items():
        if not device.is_mower:
            continue
        entities.extend([
            CramerStartButton(coordinator, device_id),
            CramerStopButton(coordinator, device_id),
            CramerParkButton(coordinator, device_id),
        ])
    async_add_entities(entities)


class _CramerMowerButton(CoordinatorEntity[CramerConnectCoordinator], ButtonEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CramerConnectCoordinator,
        device_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id

    @property
    def _device(self) -> CramerDevice:
        return self.coordinator.data[self._device_id]

    @property
    def available(self) -> bool:
        return (
            self._device_id in self.coordinator.data
            and self._device.is_online
        )

    @property
    def device_info(self) -> DeviceInfo:
        device = self._device
        return DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.name,
            manufacturer="Cramer",
            model=device.mower_model or device.product_code or "Robotic Mower",
            serial_number=device.serial_number,
        )

    async def _send(self, hub_method: str) -> None:
        device = self._device
        try:
            await self.coordinator.client.send_command(
                self.coordinator.auth,
                device.product_id,
                device.device_id,
                hub_method,
            )
        except CramerConnectTokenExpiredError:
            _LOGGER.debug("GUC token expired, re-authenticating and retrying")
            await self.coordinator.force_reauth()
            fresh_device = self.coordinator.data.get(self._device_id, device)
            await self.coordinator.client.send_command(
                self.coordinator.auth,
                fresh_device.product_id,
                fresh_device.device_id,
                hub_method,
            )


class CramerStartButton(_CramerMowerButton):
    _attr_name = "Start mowing"
    _attr_icon = "mdi:play"

    def __init__(self, coordinator: CramerConnectCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_start"

    async def async_press(self) -> None:
        _LOGGER.debug("SignalR StartMowerRequest: %s", self._device_id)
        await self._send(_CMD_START)
        await self.coordinator.async_request_refresh()


class CramerStopButton(_CramerMowerButton):
    _attr_name = "Return to dock"
    _attr_icon = "mdi:stop"

    def __init__(self, coordinator: CramerConnectCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_stop"

    async def async_press(self) -> None:
        _LOGGER.debug("SignalR ParkMowerRequest: %s", self._device_id)
        await self._send(_CMD_STOP)
        await self.coordinator.async_request_refresh()


class CramerParkButton(_CramerMowerButton):
    _attr_name = "Park until next schedule"
    _attr_icon = "mdi:home"

    def __init__(self, coordinator: CramerConnectCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_park"

    async def async_press(self) -> None:
        _LOGGER.debug("SignalR PauseMowerRequest: %s", self._device_id)
        await self._send(_CMD_PARK)
        await self.coordinator.async_request_refresh()
