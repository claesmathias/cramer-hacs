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
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfTime
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
        key="charging_time",
        name="Total charging time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.HOURS,
        icon="mdi:battery-charging",
    ),
    SensorEntityDescription(
        key="error_count",
        name="Error count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:alert-circle",
    ),
    SensorEntityDescription(
        key="software_version",
        name="Software version",
        icon="mdi:chip",
    ),
    SensorEntityDescription(
        key="distance",
        name="Total mowing distance",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=2,
        icon="mdi:map-marker-distance",
    ),
    SensorEntityDescription(
        key="latitude",
        name="Latitude",
        native_unit_of_measurement="°",
        suggested_display_precision=6,
        icon="mdi:latitude",
    ),
    SensorEntityDescription(
        key="longitude",
        name="Longitude",
        native_unit_of_measurement="°",
        suggested_display_precision=6,
        icon="mdi:longitude",
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
            model=device.mower_model or device.product_code or "Robotic Mower",
            serial_number=device.serial_number,
        )

    @property
    def available(self) -> bool:
        if self._device_id not in self.coordinator.data:
            return False
        key = self.entity_description.key
        # Historical stats are always available regardless of online status
        if key in ("cutting_time", "running_time", "charging_time", "error_count"):
            return True
        # These sensors are only available when the API provides the data
        if key == "distance":
            return self._device.distance_m is not None
        if key == "software_version":
            return self._device.software_version is not None
        if key in ("latitude", "longitude"):
            return self._device.latitude is not None and self._device.longitude is not None
        # Next start is only meaningful when there is actually a schedule
        if key == "next_start":
            return self._device.is_online and self._device.next_start_ts is not None
        # All other real-time sensors require the device to be online
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

        if key == "charging_time":
            if device.charging_time_s is None:
                return None
            return round(device.charging_time_s / 3600, 1)

        if key == "error_count":
            return device.error_count

        if key == "software_version":
            return device.software_version

        if key == "distance":
            if device.distance_m is None:
                return None
            return round(device.distance_m / 1000, 3)

        if key == "latitude":
            return device.latitude

        if key == "longitude":
            return device.longitude

        return None

    @property
    def extra_state_attributes(self) -> dict:
        if self.entity_description.key == "state":
            return {"raw_state": self._device.state}
        return {}
