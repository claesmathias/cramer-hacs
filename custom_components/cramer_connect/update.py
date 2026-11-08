"""Firmware update entity for Cramer Connect (read-only).

Installed version: dp[117] (main application version).
Latest version:    dp[119] header of the firmware offered to the mower.
The update is installed by the mower itself; there is no install action.
"""
from __future__ import annotations

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import CramerDevice
from .const import DOMAIN
from .coordinator import CramerConnectCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CramerConnectCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        CramerFirmwareUpdate(coordinator, device_id)
        for device_id, device in coordinator.data.items()
        if device.is_mower
    )


class CramerFirmwareUpdate(CoordinatorEntity[CramerConnectCoordinator], UpdateEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "firmware"
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: CramerConnectCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_firmware"

    @property
    def _device(self) -> CramerDevice:
        return self.coordinator.data[self._device_id]

    @property
    def available(self) -> bool:
        return (
            self._device_id in self.coordinator.data
            and self._device.software_version is not None
        )

    @property
    def installed_version(self) -> str | None:
        return self._device.software_version

    @property
    def latest_version(self) -> str | None:
        # Without an offered firmware header, assume the installed one is current
        return self._device.latest_software_version or self._device.software_version

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
