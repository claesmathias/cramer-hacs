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
    CramerPauseButton,
    minutes_until_end_of_day,
)
from custom_components.cramer_connect.const import (
    CMD_START,
    CMD_STOP,
    CMD_STOP_SECONDARY_AREA,
)
from custom_components.cramer_connect.lawn_mower import CramerLawnMower
from homeassistant.exceptions import HomeAssistantError

PARK_FOREVER = "0007000b003e6000A005e60002feff"


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
    coord.auth.has_mqtt_credentials = True
    coord.client = MagicMock()
    coord.async_send_command = AsyncMock()
    coord.async_request_refresh = AsyncMock()
    coord.set_pending_schedule = MagicMock()
    coord.pin = None
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
# Buttons
# ---------------------------------------------------------------------------

class TestStartButton:
    def test_unique_id(self):
        assert _start_button()._attr_unique_id == "dev-1_start"

    def test_available_when_online(self):
        assert _start_button().available is True

    def test_unavailable_when_offline(self):
        assert _start_button(_device(is_online=False)).available is False

    def test_unavailable_without_mqtt_credentials(self):
        btn = _start_button()
        btn.coordinator.auth.has_mqtt_credentials = False
        assert btn.available is False

    def test_device_info_identifiers(self):
        from custom_components.cramer_connect.const import DOMAIN
        info = _start_button().device_info
        assert (DOMAIN, "dev-1") in info["identifiers"]

    async def test_press_sends_start_command(self):
        btn = _start_button()
        await btn.async_press()
        btn.coordinator.async_send_command.assert_awaited_once_with("dev-1", CMD_START)
        assert CMD_START == "0007000d003a6000A007e4000400000000"

    async def test_press_requests_refresh(self):
        btn = _start_button()
        await btn.async_press()
        btn.coordinator.async_request_refresh.assert_awaited_once()

    async def test_press_with_pin_when_security_level_requires_it(self):
        btn = _start_button(_device(security_level=1))
        btn.coordinator.pin = "1234"  # 0x04d2 → little-endian d204
        await btn.async_press()
        btn.coordinator.async_send_command.assert_awaited_once_with(
            "dev-1", "0007000d003a6000A007e400040000d204"
        )

    async def test_pin_not_sent_when_not_required(self):
        btn = _start_button(_device(security_level=0))
        btn.coordinator.pin = "1234"
        await btn.async_press()
        btn.coordinator.async_send_command.assert_awaited_once_with("dev-1", CMD_START)

    async def test_missing_pin_raises(self):
        btn = _start_button(_device(security_level=9))
        with pytest.raises(HomeAssistantError):
            await btn.async_press()
        btn.coordinator.async_send_command.assert_not_awaited()

    async def test_api_error_becomes_ha_error(self):
        from custom_components.cramer_connect.api import CramerConnectApiError
        btn = _start_button()
        btn.coordinator.async_send_command.side_effect = CramerConnectApiError("x")
        with pytest.raises(HomeAssistantError):
            await btn.async_press()


class TestPauseButton:
    async def test_press_sends_stop(self):
        dev = _device()
        btn = CramerPauseButton(_coordinator(dev), dev.device_id)
        assert btn._attr_unique_id == "dev-1_pause"
        await btn.async_press()
        btn.coordinator.async_send_command.assert_awaited_once_with("dev-1", CMD_STOP)

    async def test_secondary_area_uses_its_own_stop(self):
        dev = _device(state="12")
        btn = CramerPauseButton(_coordinator(dev), dev.device_id)
        await btn.async_press()
        btn.coordinator.async_send_command.assert_awaited_once_with(
            "dev-1", CMD_STOP_SECONDARY_AREA
        )


class TestStopButton:
    def test_unique_id(self):
        assert _stop_button()._attr_unique_id == "dev-1_stop"

    def test_unavailable_when_offline(self):
        assert _stop_button(_device(is_online=False)).available is False

    async def test_press_parks_until_further_notice(self):
        btn = _stop_button()
        await btn.async_press()
        btn.coordinator.async_send_command.assert_awaited_once_with("dev-1", PARK_FOREVER)


class TestParkButton:
    def test_unique_id(self):
        assert _park_button()._attr_unique_id == "dev-1_park"

    async def test_press_parks_for_rest_of_day(self):
        btn = _park_button()
        await btn.async_press()
        (_, payload), _ = btn.coordinator.async_send_command.await_args
        assert payload.startswith("0007000b003e6000A005e60002")
        minutes = int.from_bytes(bytes.fromhex(payload[-4:]), "little")
        assert 1 <= minutes <= 24 * 60

    def test_minutes_until_end_of_day_range(self):
        assert 1 <= minutes_until_end_of_day() <= 24 * 60


# ---------------------------------------------------------------------------
# Lawn mower entity
# ---------------------------------------------------------------------------

def _mower(device: CramerDevice | None = None) -> CramerLawnMower:
    dev = device or _device()
    return CramerLawnMower(_coordinator(dev), dev.device_id)


class TestLawnMower:
    @pytest.mark.parametrize("state,activity", [
        ("4", "mowing"), ("12", "mowing"), ("7", "docked"), ("2", "docked"),
        ("3", "paused"), ("6", "returning"), ("8", "error"), ("11", "error"),
    ])
    def test_activity(self, state, activity):
        assert _mower(_device(state=state)).activity == activity

    def test_unknown_state_activity_none(self):
        assert _mower(_device(state=None)).activity is None

    def test_reason_attribute(self):
        attrs = _mower(_device(state="2", source_for_next_start=4)).extra_state_attributes
        assert attrs["reason"] == "parked_by_user"

    async def test_start_mowing(self):
        m = _mower()
        await m.async_start_mowing()
        m.coordinator.async_send_command.assert_awaited_once_with("dev-1", CMD_START)

    async def test_pause(self):
        m = _mower()
        await m.async_pause()
        m.coordinator.async_send_command.assert_awaited_once_with("dev-1", CMD_STOP)

    async def test_dock(self):
        m = _mower()
        await m.async_dock()
        m.coordinator.async_send_command.assert_awaited_once_with("dev-1", PARK_FOREVER)

    async def test_park_service_with_duration(self):
        m = _mower()
        await m.async_park_service(duration=120)
        m.coordinator.async_send_command.assert_awaited_once_with(
            "dev-1", "0007000b003e6000A005e600027800"
        )


class TestButtonDefaults:
    def test_start_and_pause_disabled_by_default(self):
        assert CramerStartButton._attr_entity_registry_enabled_default is False
        assert CramerPauseButton._attr_entity_registry_enabled_default is False

    def test_park_buttons_enabled_by_default(self):
        assert getattr(CramerStopButton, "_attr_entity_registry_enabled_default", True)
        assert getattr(CramerParkButton, "_attr_entity_registry_enabled_default", True)


# ---------------------------------------------------------------------------
# Schedule services, calendar, set clock
# ---------------------------------------------------------------------------

from datetime import datetime as _dt, time as _t, timedelta as _td  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

from custom_components.cramer_connect.api import OFF_TIMER, ScheduleTimer  # noqa: E402
from custom_components.cramer_connect.button import CramerSetClockButton  # noqa: E402
from custom_components.cramer_connect.calendar import (  # noqa: E402
    CramerScheduleCalendar,
    schedule_events,
)

_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
TUE_10_TO_17 = tuple(
    (ScheduleTimer(10, 0, 420, True), OFF_TIMER) if d == "tuesday" else (OFF_TIMER, OFF_TIMER)
    for d in _DAYS
)
TZ = ZoneInfo("Europe/Brussels")


class TestSetSchedule:
    async def test_set_days_keeps_other_days(self):
        m = _mower(_device(schedule=TUE_10_TO_17))
        await m.async_set_schedule(
            days=["monday", "friday"], timer_1_start=_t(9, 0), timer_1_end=_t(12, 30),
        )
        (_, payload), _ = m.coordinator.async_send_command.await_args
        body = bytes.fromhex(payload[26:])
        mon, tue, fri = body[0:10], body[10:20], body[40:50]
        assert mon[:5] == bytes([9, 0, 210, 0, 1])
        assert fri[:5] == bytes([9, 0, 210, 0, 1])
        assert tue[:5] == bytes([10, 0, 0xA4, 0x01, 1])
        m.coordinator.set_pending_schedule.assert_called_once()
        (_, sched), _ = m.coordinator.set_pending_schedule.call_args
        assert sched[0][0] == ScheduleTimer(9, 0, 210, True)

    async def test_no_times_turns_day_off(self):
        m = _mower(_device(schedule=TUE_10_TO_17))
        await m.async_set_schedule(days=["tuesday"])
        (_, sched), _ = m.coordinator.set_pending_schedule.call_args
        assert not any(t.active for day in sched for t in day)

    async def test_end_midnight(self):
        m = _mower(_device(schedule=TUE_10_TO_17))
        await m.async_set_schedule(days=["sunday"], timer_1_start=_t(20, 0), timer_1_end=_t(0, 0))
        (_, sched), _ = m.coordinator.set_pending_schedule.call_args
        assert sched[6][0] == ScheduleTimer(20, 0, 240, True)

    @pytest.mark.parametrize("kwargs", [
        dict(timer_1_start=_t(12, 0), timer_1_end=_t(11, 0)),  # end before start
        dict(timer_1_start=_t(12, 0)),  # missing end
        dict(timer_1_start=_t(9, 0), timer_1_end=_t(12, 0),
             timer_2_start=_t(11, 0), timer_2_end=_t(13, 0)),  # overlap
    ])
    async def test_invalid_timers_rejected(self, kwargs):
        m = _mower(_device(schedule=TUE_10_TO_17))
        with pytest.raises(HomeAssistantError):
            await m.async_set_schedule(days=["monday"], **kwargs)
        m.coordinator.async_send_command.assert_not_awaited()

    async def test_unknown_schedule_needs_all_days(self):
        m = _mower(_device(schedule=None))
        with pytest.raises(HomeAssistantError):
            await m.async_set_schedule(days=["monday"], timer_1_start=_t(9, 0), timer_1_end=_t(10, 0))
        await m.async_set_schedule(days=list(_DAYS), timer_1_start=_t(9, 0), timer_1_end=_t(10, 0))
        m.coordinator.async_send_command.assert_awaited_once()

    async def test_nonstop_and_cancel(self):
        m = _mower()
        await m.async_start_nonstop_mowing(days=7)
        m.coordinator.async_send_command.assert_awaited_with(
            "dev-1", "0007000c00366000A0064a0103602701"  # 10080 min
        )
        await m.async_cancel_nonstop_mowing()
        m.coordinator.async_send_command.assert_awaited_with(
            "dev-1", "0007000c00366000A0064a0103000000"
        )

    async def test_set_clock_button(self):
        dev = _device()
        btn = CramerSetClockButton(_coordinator(dev), dev.device_id)
        assert btn._attr_entity_category == "config"
        await btn.async_press()
        (_, payload), _ = btn.coordinator.async_send_command.await_args
        assert payload.startswith("0007001100566000A00b9a0008") and len(payload) == 26 + 16


class TestScheduleCalendar:
    def test_weekly_events_in_range(self):
        start = _dt(2026, 11, 2, tzinfo=TZ)  # Monday
        events = schedule_events(TUE_10_TO_17, start, start + _td(days=14))
        assert [e.start for e in events] == [
            _dt(2026, 11, 3, 10, 0, tzinfo=TZ), _dt(2026, 11, 10, 10, 0, tzinfo=TZ),
        ]
        assert events[0].end == _dt(2026, 11, 3, 17, 0, tzinfo=TZ)
        assert events[0].summary == "Mowing"

    def test_window_in_progress_is_included(self):
        start = _dt(2026, 11, 3, 12, 0, tzinfo=TZ)
        events = schedule_events(TUE_10_TO_17, start, start + _td(hours=1))
        assert len(events) == 1

    def test_no_events_outside_range(self):
        start = _dt(2026, 11, 4, tzinfo=TZ)  # Wednesday
        assert schedule_events(TUE_10_TO_17, start, start + _td(days=2)) == []

    def test_available_offline_with_schedule(self):
        dev = _device(is_online=False, schedule=TUE_10_TO_17)
        cal = CramerScheduleCalendar(_coordinator(dev), dev.device_id)
        assert cal.available is True
        assert cal._attr_unique_id == "dev-1_schedule"

    def test_unavailable_without_schedule(self):
        dev = _device(schedule=None)
        assert CramerScheduleCalendar(_coordinator(dev), dev.device_id).available is False

    def test_next_event(self):
        dev = _device(schedule=TUE_10_TO_17)
        ev = CramerScheduleCalendar(_coordinator(dev), dev.device_id).event
        assert ev is not None and ev.start.weekday() == 1

    async def test_get_events(self):
        dev = _device(schedule=TUE_10_TO_17)
        cal = CramerScheduleCalendar(_coordinator(dev), dev.device_id)
        start = _dt(2026, 11, 2, tzinfo=TZ)
        assert len(await cal.async_get_events(None, start, start + _td(days=7))) == 1
