"""Unit tests for device_tracker and button entities."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.cramer_connect.api import CramerDevice
from custom_components.cramer_connect.device_tracker import CramerMowerTracker
from custom_components.cramer_connect.button import (
    CramerStartButton,
    CramerStopButton,
    CramerParkButton,
    _CMD_START,
    _CMD_STOP,
    _CMD_PARK,
)


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
    coord.auth = MagicMock()
    coord.client = MagicMock()
    coord.client.send_command = AsyncMock()
    coord.async_request_refresh = AsyncMock()
    return coord


def _tracker(device: CramerDevice | None = None) -> CramerMowerTracker:
    dev = device or _device()
    coord = _coordinator(dev)
    return CramerMowerTracker(coord, dev.device_id)


def _start_button(device: CramerDevice | None = None) -> CramerStartButton:
    dev = device or _device()
    coord = _coordinator(dev)
    return CramerStartButton(coord, dev.device_id)


def _stop_button(device: CramerDevice | None = None) -> CramerStopButton:
    dev = device or _device()
    coord = _coordinator(dev)
    return CramerStopButton(coord, dev.device_id)


def _park_button(device: CramerDevice | None = None) -> CramerParkButton:
    dev = device or _device()
    coord = _coordinator(dev)
    return CramerParkButton(coord, dev.device_id)


# ---------------------------------------------------------------------------
# Device tracker
# ---------------------------------------------------------------------------

class TestMowerTracker:
    def test_latitude(self):
        assert _tracker().latitude == 52.0

    def test_longitude(self):
        assert _tracker().longitude == 5.0

    def test_battery_level(self):
        assert _tracker().battery_level == 78

    def test_available_when_coordinates_present(self):
        assert _tracker().available is True

    def test_unavailable_when_no_latitude(self):
        assert _tracker(_device(latitude=None)).available is False

    def test_unavailable_when_no_longitude(self):
        assert _tracker(_device(longitude=None)).available is False

    def test_unique_id_suffix(self):
        assert _tracker()._attr_unique_id == "dev-1_tracker"

    def test_extra_attrs_contain_state_and_online(self):
        attrs = _tracker().extra_state_attributes
        assert "state" in attrs
        assert "is_online" in attrs
        assert attrs["is_online"] is True

    def test_extra_attrs_state_label_is_string(self):
        attrs = _tracker().extra_state_attributes
        assert isinstance(attrs["state"], str)

    def test_device_info_identifiers(self):
        from custom_components.cramer_connect.const import DOMAIN
        info = _tracker().device_info
        assert (DOMAIN, "dev-1") in info["identifiers"]

    def test_device_info_model_from_mower_model(self):
        info = _tracker().device_info
        assert info["model"] == "Test RM1000"

    def test_device_info_falls_back_to_product_code(self):
        info = _tracker(_device(mower_model=None)).device_info
        assert info["model"] == "RLM1"

    def test_none_battery_when_not_set(self):
        assert _tracker(_device(battery=None)).battery_level is None


# ---------------------------------------------------------------------------
# Start button
# ---------------------------------------------------------------------------

class TestStartButton:
    def test_unique_id(self):
        assert _start_button()._attr_unique_id == "dev-1_start"

    def test_available_when_online(self):
        assert _start_button().available is True

    def test_unavailable_when_offline(self):
        assert _start_button(_device(is_online=False)).available is False

    def test_device_info_identifiers(self):
        from custom_components.cramer_connect.const import DOMAIN
        info = _start_button().device_info
        assert (DOMAIN, "dev-1") in info["identifiers"]

    @pytest.mark.asyncio
    async def test_press_sends_start_command(self):
        dev = _device()
        coord = _coordinator(dev)
        btn = CramerStartButton(coord, dev.device_id)
        await btn.async_press()
        coord.client.send_command.assert_awaited_once_with(
            coord.auth, dev.product_id, dev.device_id, _CMD_START
        )

    @pytest.mark.asyncio
    async def test_press_requests_refresh(self):
        dev = _device()
        coord = _coordinator(dev)
        btn = CramerStartButton(coord, dev.device_id)
        await btn.async_press()
        coord.async_request_refresh.assert_awaited_once()


# ---------------------------------------------------------------------------
# Stop button
# ---------------------------------------------------------------------------

class TestStopButton:
    def test_unique_id(self):
        assert _stop_button()._attr_unique_id == "dev-1_stop"

    def test_available_when_online(self):
        assert _stop_button().available is True

    def test_unavailable_when_offline(self):
        assert _stop_button(_device(is_online=False)).available is False

    @pytest.mark.asyncio
    async def test_press_sends_stop_command(self):
        dev = _device()
        coord = _coordinator(dev)
        btn = CramerStopButton(coord, dev.device_id)
        await btn.async_press()
        coord.client.send_command.assert_awaited_once_with(
            coord.auth, dev.product_id, dev.device_id, _CMD_STOP
        )


# ---------------------------------------------------------------------------
# Park button
# ---------------------------------------------------------------------------

class TestParkButton:
    def test_unique_id(self):
        assert _park_button()._attr_unique_id == "dev-1_park"

    def test_available_when_online(self):
        assert _park_button().available is True

    def test_unavailable_when_offline(self):
        assert _park_button(_device(is_online=False)).available is False

    @pytest.mark.asyncio
    async def test_press_sends_park_command(self):
        dev = _device()
        coord = _coordinator(dev)
        btn = CramerParkButton(coord, dev.device_id)
        await btn.async_press()
        coord.client.send_command.assert_awaited_once_with(
            coord.auth, dev.product_id, dev.device_id, _CMD_PARK
        )

    def test_park_and_stop_use_different_hub_methods(self):
        assert _CMD_STOP != _CMD_PARK
