"""Binary sensor entities for Cramer Connect."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
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
    entities = [
        CramerOnlineSensor(coordinator, device_id)
        for device_id, device in coordinator.data.items()
        if device.is_mower
    ]
    async_add_entities(entities)


class CramerOnlineSensor(CoordinatorEntity[CramerConnectCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = "Online"
    _attr_icon = "mdi:wifi"

    def __init__(
        self,
        coordinator: CramerConnectCoordinator,
        device_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_online"

    @property
    def _device(self) -> CramerDevice:
        return self.coordinator.data[self._device_id]

    @property
    def device_info(self) -> DeviceInfo:
        device = self._device
        return DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.name,
            manufacturer="Cramer",
            model=device.product_code or "Robotic Mower",
            serial_number=device.serial_number,
        )

    @property
    def available(self) -> bool:
        return self._device_id in self.coordinator.data

    @property
    def is_on(self) -> bool:
        return self._device.is_online
