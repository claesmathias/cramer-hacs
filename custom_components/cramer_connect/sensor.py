"""Sensor entities for Cramer Connect."""
from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import CramerDevice
from .const import DOMAIN
from .coordinator import CramerConnectCoordinator

MOWER_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="state",
        name="State",
        icon="mdi:robot-mower",
    ),
    SensorEntityDescription(
        key="battery",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery",
    ),
    SensorEntityDescription(
        key="next_start",
        name="Next start",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-start",
    ),
    SensorEntityDescription(
        key="cutting_time",
        name="Total mowing time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.HOURS,
        icon="mdi:timer",
    ),
    SensorEntityDescription(
        key="running_time",
        name="Total running time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.HOURS,
        icon="mdi:timer-outline",
    ),
    SensorEntityDescription(
        key="error_count",
        name="Error count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:alert-circle",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CramerConnectCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []

    for device_id, device in coordinator.data.items():
        if not device.is_mower:
            continue
        for description in MOWER_SENSORS:
            entities.append(CramerMowerSensor(coordinator, device_id, description))

    async_add_entities(entities)


class CramerMowerSensor(CoordinatorEntity[CramerConnectCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CramerConnectCoordinator,
        device_id: str,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

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
        if self._device_id not in self.coordinator.data:
            return False
        # Statistics are historical and always available; real-time ones need online
        if self.entity_description.key in ("cutting_time", "running_time", "error_count"):
            return True
        return self._device.is_online

    @property
    def native_value(self) -> str | int | float | datetime | None:
        device = self._device
        key = self.entity_description.key

        if key == "state":
            return device.state_label

        if key == "battery":
            return device.battery

        if key == "next_start":
            if device.next_start_ts is None:
                return None
            return datetime.fromtimestamp(device.next_start_ts, tz=timezone.utc)

        if key == "cutting_time":
            if device.cutting_time_s is None:
                return None
            return round(device.cutting_time_s / 3600, 1)

        if key == "running_time":
            if device.running_time_s is None:
                return None
            return round(device.running_time_s / 3600, 1)

        if key == "error_count":
            return device.error_count

        return None

    @property
    def extra_state_attributes(self) -> dict:
        if self.entity_description.key == "state":
            return {"raw_state": self._device.state}
        return {}
