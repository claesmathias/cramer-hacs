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
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .api import CramerDevice
from .const import DOMAIN, MOWER_STATE_OPTIONS
from .coordinator import CramerConnectCoordinator

MOWER_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="state",
        translation_key="state",
        device_class=SensorDeviceClass.ENUM,
        options=MOWER_STATE_OPTIONS,
    ),
    SensorEntityDescription(
        key="status",
        translation_key="status",
    ),
    SensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="next_start",
        translation_key="next_start",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="last_seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="cutting_time",
        translation_key="cutting_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="running_time",
        translation_key="running_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="charging_time",
        translation_key="charging_time",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="distance",
        translation_key="distance",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="error_count",
        translation_key="error_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="last_error",
        translation_key="last_error",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="software_version",
        translation_key="software_version",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="lte_signal",
        translation_key="lte_signal",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Shown on the map by the device tracker already — off by default
    SensorEntityDescription(
        key="latitude",
        translation_key="latitude",
        native_unit_of_measurement="°",
        suggested_display_precision=6,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="longitude",
        translation_key="longitude",
        native_unit_of_measurement="°",
        suggested_display_precision=6,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)

# Sensors whose value comes from the last report and stays valid offline
_ALWAYS_AVAILABLE = {
    "cutting_time", "running_time", "charging_time", "error_count",
    "last_error", "last_seen", "status",
}
# Sensors that are only available when the mower reported the value
_OPTIONAL_FIELDS = {
    "distance": "distance_m",
    "software_version": "software_version",
    "wifi_signal": "wifi_signal",
    "lte_signal": "lte_signal",
    "last_seen": "last_seen",
}

# Status sentences, mirroring the app's home screen
_STATUS_TEXT = {
    "starting_up": "Starting up",
    "stop_button_pressed": "Stop button pressed",
    "parked": "Parked",
    "paused": "Paused",
    "mowing": "Mowing",
    "leaving_charging_station": "Leaving charging station",
    "searching_charging_station": "Searching for charging station",
    "charging": "Charging",
    "error": "Error",
    "fatal_error": "Fatal error",
    "recovery_state": "Recovery state",
    "alarm_state": "Alarm",
    "mowing_secondary_area": "Mowing secondary area",
    "parked_by_schedule": "Parked by schedule",
    "parked_max_day_cutting": "Max day cutting time reached",
    "parked_by_user": "Parked by user",
    "parked_by_rain_guard": "Parked by rain guard",
    "parked_by_frost_guard": "Parked by frost guard",
    "energy_saving_mode": "Energy saving mode",
}


def _format_time(ts: int) -> str:
    """'14:00' for today, 'Tue 14:00' for another day (local time)."""
    when = dt_util.as_local(datetime.fromtimestamp(ts, tz=timezone.utc))
    return when.strftime("%H:%M" if when.date() == dt_util.now().date() else "%a %H:%M")


def status_text(device: CramerDevice) -> str:
    """One-line status like the app: 'Parked by user until Tue 14:00'."""
    label = device.state_label
    if label == "unknown":
        return "Unknown"
    text = _STATUS_TEXT.get(label, label.replace("_", " ").capitalize())
    if device.state in ("8", "9", "10", "11") and device.last_error:
        text = f"{text}: {device.last_error}"
    elif device.state == "4" and device.nonstop_mowing:
        text = "Mowing nonstop"
        if device.next_start_ts is not None:
            text = f"{text} until {_format_time(device.next_start_ts)}"
    elif device.state in ("2", "7"):
        if device.next_start_ts is not None:
            text = f"{text} until {_format_time(device.next_start_ts)}"
        elif label == "parked_by_user":
            text = f"{text} until further notice"
    if not device.is_online:
        text = f"{text} (offline)"
    return text


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CramerConnectCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        CramerMowerSensor(coordinator, device_id, description)
        for device_id, device in coordinator.data.items()
        if device.is_mower
        for description in MOWER_SENSORS
    )


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
            sw_version=device.software_version,
        )

    @property
    def available(self) -> bool:
        if self._device_id not in self.coordinator.data:
            return False
        device = self._device
        key = self.entity_description.key
        if key in _OPTIONAL_FIELDS and getattr(device, _OPTIONAL_FIELDS[key]) is None:
            return False
        if key in _ALWAYS_AVAILABLE or key in _OPTIONAL_FIELDS:
            return True
        if key in ("latitude", "longitude"):
            return device.latitude is not None and device.longitude is not None
        if key == "next_start":
            return device.is_online and device.next_start_ts is not None
        return device.is_online

    @property
    def native_value(self) -> str | int | float | datetime | None:
        device = self._device
        key = self.entity_description.key

        if key == "state":
            label = device.state_label
            return label if label in MOWER_STATE_OPTIONS else None
        if key == "status":
            return status_text(device)
        if key == "battery":
            return device.battery
        if key == "next_start":
            if device.next_start_ts is None:
                return None
            return datetime.fromtimestamp(device.next_start_ts, tz=timezone.utc)
        if key == "last_seen":
            return device.last_seen
        if key in ("cutting_time", "running_time", "charging_time"):
            seconds = getattr(device, f"{key}_s")
            return None if seconds is None else round(seconds / 3600, 1)
        if key == "distance":
            return None if device.distance_m is None else round(device.distance_m / 1000, 3)
        if key == "error_count":
            return device.error_count
        if key == "last_error":
            return device.last_error or "No error"
        if key == "software_version":
            return device.software_version
        if key == "wifi_signal":
            return device.wifi_signal
        if key == "lte_signal":
            return device.lte_signal
        if key == "latitude":
            return device.latitude
        if key == "longitude":
            return device.longitude
        return None

    @property
    def extra_state_attributes(self) -> dict:
        device = self._device
        key = self.entity_description.key
        if key == "state":
            return {
                "raw_state": device.state,
                "reason": device.next_start_reason,
                "source_for_next_start": device.source_for_next_start,
            }
        if key == "last_error":
            return {
                "error_code": device.last_error_code,
                "error_time": device.last_error_time,
            }
        return {}
