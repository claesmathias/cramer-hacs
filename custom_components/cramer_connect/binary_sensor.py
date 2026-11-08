"""Binary sensor entities for Cramer Connect."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    entities = []
    for device_id, device in coordinator.data.items():
        if not device.is_mower:
            continue
        entities.append(CramerOnlineSensor(coordinator, device_id))
        entities.append(CramerChargingSensor(coordinator, device_id))
    async_add_entities(entities)


class _CramerBinarySensor(CoordinatorEntity[CramerConnectCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _key: str

    def __init__(self, coordinator: CramerConnectCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{self._key}"

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
            model=device.mower_model or device.product_code or "Robotic Mower",
            serial_number=device.serial_number,
        )

    @property
    def available(self) -> bool:
        return self._device_id in self.coordinator.data


class CramerOnlineSensor(_CramerBinarySensor):
    _key = "online"
    _attr_translation_key = "online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        return self._device.is_online


class CramerChargingSensor(_CramerBinarySensor):
    _key = "charging"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    @property
    def available(self) -> bool:
        return super().available and self._device.is_online

    @property
    def is_on(self) -> bool:
        return self._device.is_charging
