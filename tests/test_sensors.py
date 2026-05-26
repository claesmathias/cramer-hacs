"""Unit tests for sensor and binary_sensor entities."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, PropertyMock

import pytest

from custom_components.cramer_connect.api import CramerDevice
from custom_components.cramer_connect.sensor import CramerMowerSensor, MOWER_SENSORS
from custom_components.cramer_connect.binary_sensor import CramerOnlineSensor, CramerUpdateSensor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _device(**kwargs) -> CramerDevice:
    defaults = dict(
        device_id="dev-1",
        product_id="prod-1",
        name="Test Mower",
        serial_number="SN-TEST-001",
        mac="",
        product_code="RLM1",
        state="4",
        battery=78,
        is_online=True,
        next_start_ts=1800000000,
        cutting_time_s=7200,
        running_time_s=14400,
        error_count=3,
        distance_m=5000,
        charging_time_s=3600,
        latitude=52.0,
        longitude=5.0,
        software_version="13.5.100000000",
        sw_update_available=True,
        mower_model="Test RM1000",
    )
    return CramerDevice(**{**defaults, **kwargs})


def _coordinator(device: CramerDevice) -> MagicMock:
    coord = MagicMock()
    coord.data = {device.device_id: device}
    return coord


def _sensor(key: str, device: CramerDevice | None = None) -> CramerMowerSensor:
    dev = device or _device()
    coord = _coordinator(dev)
    description = next(d for d in MOWER_SENSORS if d.key == key)
    sensor = CramerMowerSensor.__new__(CramerMowerSensor)
    sensor._device_id = dev.device_id
    sensor.entity_description = description
    sensor.coordinator = coord
    return sensor


def _update_sensor(device: CramerDevice | None = None) -> CramerUpdateSensor:
    dev = device or _device()
    coord = _coordinator(dev)
    return CramerUpdateSensor(coord, dev.device_id)


def _online_sensor(device: CramerDevice | None = None) -> CramerOnlineSensor:
    dev = device or _device()
    coord = _coordinator(dev)
    sensor = CramerOnlineSensor(coord, dev.device_id)
    return sensor


# ---------------------------------------------------------------------------
# State sensor
# ---------------------------------------------------------------------------

class TestStateSensor:
    def test_value_is_state_label(self):
        assert _sensor("state").native_value == "mowing"

    def test_unknown_state_label(self):
        assert _sensor("state", _device(state="99")).native_value == "unknown"

    def test_none_state(self):
        assert _sensor("state", _device(state=None)).native_value == "unknown"

    def test_extra_attrs_contains_raw_state(self):
        assert _sensor("state").extra_state_attributes == {"raw_state": "4"}

    def test_unavailable_when_offline(self):
        s = _sensor("state", _device(is_online=False))
        assert s.available is False

    def test_available_when_online(self):
        assert _sensor("state").available is True


# ---------------------------------------------------------------------------
# Battery sensor
# ---------------------------------------------------------------------------

class TestBatterySensor:
    def test_value_is_percentage(self):
        assert _sensor("battery").native_value == 78

    def test_none_battery(self):
        assert _sensor("battery", _device(battery=None)).native_value is None

    def test_unavailable_when_offline(self):
        assert _sensor("battery", _device(is_online=False)).available is False


# ---------------------------------------------------------------------------
# Next-start sensor
# ---------------------------------------------------------------------------

class TestNextStartSensor:
    def test_returns_utc_datetime(self):
        val = _sensor("next_start").native_value
        assert isinstance(val, datetime)
        assert val.tzinfo == timezone.utc
        assert val == datetime.fromtimestamp(1800000000, tz=timezone.utc)

    def test_none_when_no_schedule(self):
        assert _sensor("next_start", _device(next_start_ts=None)).native_value is None

    def test_unavailable_when_offline(self):
        assert _sensor("next_start", _device(is_online=False)).available is False

    def test_unavailable_when_no_schedule(self):
        assert _sensor("next_start", _device(next_start_ts=None)).available is False

    def test_available_when_online_and_scheduled(self):
        assert _sensor("next_start").available is True


# ---------------------------------------------------------------------------
# Cutting-time sensor
# ---------------------------------------------------------------------------

class TestCuttingTimeSensor:
    def test_value_in_hours(self):
        assert _sensor("cutting_time").native_value == 2.0  # 7200s / 3600

    def test_fractional_hours(self):
        val = _sensor("cutting_time", _device(cutting_time_s=5400)).native_value
        assert val == 1.5

    def test_none_when_missing(self):
        assert _sensor("cutting_time", _device(cutting_time_s=None)).native_value is None

    def test_always_available_even_offline(self):
        assert _sensor("cutting_time", _device(is_online=False)).available is True


# ---------------------------------------------------------------------------
# Running-time sensor
# ---------------------------------------------------------------------------

class TestRunningTimeSensor:
    def test_value_in_hours(self):
        assert _sensor("running_time").native_value == 4.0  # 14400s / 3600

    def test_none_when_missing(self):
        assert _sensor("running_time", _device(running_time_s=None)).native_value is None

    def test_always_available_even_offline(self):
        assert _sensor("running_time", _device(is_online=False)).available is True


# ---------------------------------------------------------------------------
# Error-count sensor
# ---------------------------------------------------------------------------

class TestErrorCountSensor:
    def test_value(self):
        assert _sensor("error_count").native_value == 3

    def test_none_when_missing(self):
        assert _sensor("error_count", _device(error_count=None)).native_value is None

    def test_always_available_even_offline(self):
        assert _sensor("error_count", _device(is_online=False)).available is True


# ---------------------------------------------------------------------------
# Device info
# ---------------------------------------------------------------------------

class TestDeviceInfo:
    def test_mower_model_takes_priority(self):
        info = _sensor("state").device_info
        assert info["model"] == "Test RM1000"

    def test_falls_back_to_product_code(self):
        dev = _device(mower_model=None)
        info = _sensor("state", dev).device_info
        assert info["model"] == "RLM1"

    def test_xlink_device_fallback_model(self):
        dev = _device(product_code="", mower_model=None)
        info = _sensor("state", dev).device_info
        assert info["model"] == "Robotic Mower"

    def test_identifiers_use_domain_and_device_id(self):
        from custom_components.cramer_connect.const import DOMAIN
        info = _sensor("state").device_info
        assert (DOMAIN, "dev-1") in info["identifiers"]

    def test_serial_number(self):
        assert _sensor("state").device_info["serial_number"] == "SN-TEST-001"


# ---------------------------------------------------------------------------
# Charging-time sensor
# ---------------------------------------------------------------------------

class TestChargingTimeSensor:
    def test_value_in_hours(self):
        assert _sensor("charging_time").native_value == 1.0  # 3600s

    def test_fractional_hours(self):
        assert _sensor("charging_time", _device(charging_time_s=5400)).native_value == 1.5

    def test_none_when_missing(self):
        assert _sensor("charging_time", _device(charging_time_s=None)).native_value is None

    def test_always_available_even_offline(self):
        assert _sensor("charging_time", _device(is_online=False)).available is True


# ---------------------------------------------------------------------------
# Software-version sensor
# ---------------------------------------------------------------------------

class TestSoftwareVersionSensor:
    def test_value(self):
        assert _sensor("software_version").native_value == "13.5.100000000"

    def test_none_when_missing(self):
        assert _sensor("software_version", _device(software_version=None)).native_value is None

    def test_unavailable_when_no_data(self):
        assert _sensor("software_version", _device(software_version=None)).available is False

    def test_available_when_data_present(self):
        assert _sensor("software_version").available is True


# ---------------------------------------------------------------------------
# Distance sensor
# ---------------------------------------------------------------------------

class TestDistanceSensor:
    def test_value_in_km(self):
        assert _sensor("distance").native_value == 5.0  # 5000m / 1000

    def test_fractional_km(self):
        assert _sensor("distance", _device(distance_m=1500)).native_value == 1.5

    def test_sub_km_precision(self):
        assert _sensor("distance", _device(distance_m=250)).native_value == 0.25

    def test_none_when_missing(self):
        assert _sensor("distance", _device(distance_m=None)).native_value is None

    def test_available_when_data_present(self):
        assert _sensor("distance").available is True

    def test_unavailable_when_no_data(self):
        assert _sensor("distance", _device(distance_m=None)).available is False


# ---------------------------------------------------------------------------
# GPS sensors
# ---------------------------------------------------------------------------

class TestGpsSensors:
    def test_latitude_value(self):
        assert _sensor("latitude").native_value == 52.0

    def test_longitude_value(self):
        assert _sensor("longitude").native_value == 5.0

    def test_latitude_none_when_no_gps(self):
        assert _sensor("latitude", _device(latitude=None)).native_value is None

    def test_longitude_none_when_no_gps(self):
        assert _sensor("longitude", _device(longitude=None)).native_value is None

    def test_unavailable_when_no_gps_data(self):
        assert _sensor("latitude", _device(latitude=None, longitude=None)).available is False
        assert _sensor("longitude", _device(latitude=None, longitude=None)).available is False

    def test_available_when_coordinates_present(self):
        assert _sensor("latitude").available is True
        assert _sensor("longitude").available is True


# ---------------------------------------------------------------------------
# Online binary sensor
# ---------------------------------------------------------------------------

class TestOnlineSensor:
    def test_is_on_when_online(self):
        assert _online_sensor().is_on is True

    def test_is_off_when_offline(self):
        assert _online_sensor(_device(is_online=False)).is_on is False

    def test_always_available(self):
        assert _online_sensor(_device(is_online=False)).available is True

    def test_device_info(self):
        from custom_components.cramer_connect.const import DOMAIN
        info = _online_sensor().device_info
        assert (DOMAIN, "dev-1") in info["identifiers"]
        assert info["name"] == "Test Mower"

    def test_unique_id_suffix(self):
        sensor = _online_sensor()
        assert sensor._attr_unique_id == "dev-1_online"


# ---------------------------------------------------------------------------
# Update available binary sensor
# ---------------------------------------------------------------------------

class TestUpdateSensor:
    def test_is_on_when_update_available(self):
        assert _update_sensor().is_on is True

    def test_is_off_when_no_update(self):
        assert _update_sensor(_device(sw_update_available=False)).is_on is False

    def test_unavailable_when_no_data(self):
        assert _update_sensor(_device(sw_update_available=None)).available is False

    def test_available_when_data_present(self):
        assert _update_sensor().available is True

    def test_unique_id_suffix(self):
        assert _update_sensor()._attr_unique_id == "dev-1_update"

    def test_device_info_uses_mower_model(self):
        from custom_components.cramer_connect.const import DOMAIN
        info = _update_sensor().device_info
        assert (DOMAIN, "dev-1") in info["identifiers"]
        assert info["model"] == "Test RM1000"
