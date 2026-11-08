"""Unit tests for sensor and binary_sensor entities."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, PropertyMock

import pytest

from custom_components.cramer_connect.api import CramerDevice
from custom_components.cramer_connect.sensor import CramerMowerSensor, MOWER_SENSORS
from custom_components.cramer_connect.binary_sensor import CramerOnlineSensor, CramerChargingSensor
from custom_components.cramer_connect.update import CramerFirmwareUpdate


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


def _update_entity(device: CramerDevice | None = None) -> CramerFirmwareUpdate:
    dev = device or _device()
    return CramerFirmwareUpdate(_coordinator(dev), dev.device_id)


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
        # ENUM sensors report None for values outside their options
        assert _sensor("state", _device(state="99")).native_value is None

    def test_none_state(self):
        assert _sensor("state", _device(state=None)).native_value is None

    def test_extra_attrs_contains_raw_state(self):
        assert _sensor("state").extra_state_attributes["raw_state"] == "4"

    def test_extra_attrs_contains_parked_reason(self):
        attrs = _sensor(
            "state", _device(state="2", source_for_next_start=2)
        ).extra_state_attributes
        assert attrs["reason"] == "parked_by_schedule"
        assert attrs["source_for_next_start"] == 2

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

class TestFirmwareUpdate:
    def test_versions(self):
        u = _update_entity(_device(software_version="13.5.1", latest_software_version="13.6.2"))
        assert u.installed_version == "13.5.1"
        assert u.latest_version == "13.6.2"

    def test_latest_defaults_to_installed(self):
        u = _update_entity(_device(software_version="13.5.1", latest_software_version=None))
        assert u.latest_version == "13.5.1"

    def test_unavailable_without_version(self):
        assert _update_entity(_device(software_version=None)).available is False

    def test_unique_id(self):
        assert _update_entity()._attr_unique_id == "dev-1_firmware"


class TestChargingSensor:
    def _sensor(self, **kw):
        dev = _device(**kw)
        return CramerChargingSensor(_coordinator(dev), dev.device_id)

    def test_charging_state(self):
        assert self._sensor(state="7").is_on is True

    def test_parked_charging_reason(self):
        assert self._sensor(state="2", source_for_next_start=1).is_on is True

    def test_mowing_not_charging(self):
        assert self._sensor(state="4").is_on is False

    def test_unavailable_offline(self):
        assert self._sensor(is_online=False).available is False


class TestLastErrorSensor:
    def test_known_error_text(self):
        s = _sensor("last_error", _device(last_error_code=53, last_error_time="2026-06-01T10:00:00Z"))
        assert s.native_value == "Mower is stuck."
        assert s.extra_state_attributes == {
            "error_code": 53, "error_time": "2026-06-01T10:00:00Z",
        }

    def test_unknown_error_code(self):
        assert _sensor("last_error", _device(last_error_code=999)).native_value == "Error 999"

    def test_zero_event_is_unknown_error(self):
        assert _sensor("last_error", _device(last_error_code=0)).native_value == "Unknown error"

    def test_no_error(self):
        assert _sensor("last_error").native_value == "No error"

    def test_available_when_offline(self):
        assert _sensor("last_error", _device(is_online=False)).available is True


class TestExpandedState:
    @pytest.mark.parametrize("source,expected", [
        (1, "charging"), (2, "parked_by_schedule"), (3, "parked_max_day_cutting"),
        (4, "parked_by_user"), (5, "parked_by_rain_guard"),
        (6, "parked_by_frost_guard"), (7, "energy_saving_mode"), (0, "parked"),
        (None, "parked"),
    ])
    def test_parked_split_by_reason(self, source, expected):
        s = _sensor("state", _device(state="2", source_for_next_start=source))
        assert s.native_value == expected

    def test_every_value_is_an_option(self):
        from custom_components.cramer_connect.const import MOWER_STATE_OPTIONS
        desc = next(d for d in MOWER_SENSORS if d.key == "state")
        assert desc.options == MOWER_STATE_OPTIONS
        assert desc.device_class == "enum"


class TestStatusSensor:
    def test_mowing(self):
        assert _sensor("status").native_value == "Mowing"

    def test_parked_by_user_until_further_notice(self):
        s = _sensor("status", _device(state="2", source_for_next_start=4, next_start_ts=None))
        assert s.native_value == "Parked by user until further notice"

    def test_charging_until_time(self):
        s = _sensor("status", _device(state="7", next_start_ts=1800000000))
        assert s.native_value.startswith("Charging until ")

    def test_error_includes_error_text(self):
        s = _sensor("status", _device(state="9", last_error_code=53))
        assert s.native_value == "Fatal error: Mower is stuck."

    def test_offline_suffix(self):
        s = _sensor("status", _device(state="1", is_online=False))
        assert s.native_value == "Stop button pressed (offline)"
        assert s.available is True


class TestLastSeenAndSignal:
    def test_last_seen(self):
        ts = datetime(2026, 11, 5, 4, 33, tzinfo=timezone.utc)
        s = _sensor("last_seen", _device(last_seen=ts, is_online=False))
        assert s.native_value == ts
        assert s.available is True

    def test_last_seen_unavailable_when_unknown(self):
        assert _sensor("last_seen").available is False

    def test_wifi_signal(self):
        s = _sensor("wifi_signal", _device(wifi_signal=83))
        assert s.native_value == 83 and s.available is True

    def test_lte_signal_unavailable_when_missing(self):
        assert _sensor("lte_signal").available is False


class TestEntityCategories:
    def _desc(self, key):
        return next(d for d in MOWER_SENSORS if d.key == key)

    @pytest.mark.parametrize("key", [
        "error_count", "last_error", "software_version", "wifi_signal",
        "lte_signal", "latitude", "longitude",
    ])
    def test_diagnostic(self, key):
        assert self._desc(key).entity_category == "diagnostic"

    @pytest.mark.parametrize("key", ["latitude", "longitude"])
    def test_coordinates_disabled_by_default(self, key):
        assert self._desc(key).entity_registry_enabled_default is False

    @pytest.mark.parametrize("key", ["cutting_time", "running_time", "charging_time", "distance"])
    def test_whole_number_display(self, key):
        assert self._desc(key).suggested_display_precision == 0

    def test_all_named_via_translations(self):
        import json
        from pathlib import Path
        strings = json.loads((Path(__file__).parent.parent / "custom_components/cramer_connect/strings.json").read_text())
        icons = json.loads((Path(__file__).parent.parent / "custom_components/cramer_connect/icons.json").read_text())
        for d in MOWER_SENSORS:
            if d.key == "battery":
                continue  # named by its device class
            assert d.translation_key in strings["entity"]["sensor"], d.key
            assert d.translation_key in icons["entity"]["sensor"], d.key
            assert not getattr(d, "name", None) and not getattr(d, "icon", None)


class TestNonstopStatus:
    def test_nonstop_mowing_until(self):
        s = _sensor("status", _device(state="4", source_for_next_start=52, next_start_ts=1800000000))
        assert s.native_value.startswith("Mowing nonstop until ")

    def test_nonstop_without_end(self):
        s = _sensor("status", _device(state="4", source_for_next_start=53, next_start_ts=None))
        assert s.native_value == "Mowing nonstop"
