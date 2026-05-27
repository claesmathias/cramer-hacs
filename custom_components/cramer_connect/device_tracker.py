"""Device tracker entity for Cramer Connect — shows mower on the HA map."""
from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
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
        CramerMowerTracker(coordinator, device_id)
        for device_id, device in coordinator.data.items()
        if device.is_mower
    ]
    async_add_entities(entities)


class CramerMowerTracker(CoordinatorEntity[CramerConnectCoordinator], TrackerEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_icon = "mdi:robot-mower"
    _attr_source_type = SourceType.GPS

    def __init__(
        self,
        coordinator: CramerConnectCoordinator,
        device_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_tracker"

    @property
    def _device(self) -> CramerDevice:
        return self.coordinator.data[self._device_id]

    @property
    def available(self) -> bool:
        return (
            self._device_id in self.coordinator.data
            and self._device.latitude is not None
            and self._device.longitude is not None
        )

    @property
    def latitude(self) -> float | None:
        return self._device.latitude

    @property
    def longitude(self) -> float | None:
        return self._device.longitude

    @property
    def battery_level(self) -> int | None:
        return self._device.battery

    @property
    def extra_state_attributes(self) -> dict:
        device = self._device
        return {
            "state": device.state_label,
            "is_online": device.is_online,
        }

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
