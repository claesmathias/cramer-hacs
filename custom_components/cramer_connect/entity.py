"""Shared base entity and command helpers for Cramer Connect."""
from __future__ import annotations

from collections.abc import Callable
from datetime import time as dt_time

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .api import (
    OFF_TIMER,
    CramerConnectApiError,
    CramerDevice,
    ScheduleTimer,
    build_nonstop_command,
    build_schedule_command,
    build_set_clock_command,
    build_park_command,
    build_start_command,
    build_stop_command,
)
from .const import DOMAIN, SCHEDULE_DAYS
from .coordinator import CramerConnectCoordinator


class CramerMowerEntity(CoordinatorEntity[CramerConnectCoordinator]):
    """Base entity for a mower that can be commanded over MQTT."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CramerConnectCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id

    @property
    def _device(self) -> CramerDevice:
        return self.coordinator.data[self._device_id]

    @property
    def available(self) -> bool:
        return (
            self._device_id in self.coordinator.data
            and self._device.is_online
            and self.coordinator.auth.has_mqtt_credentials
        )

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

    async def _async_command(
        self, payload_hex: str, on_sent: Callable[[], None] | None = None
    ) -> None:
        try:
            await self.coordinator.async_send_command(self._device_id, payload_hex)
        except CramerConnectApiError as err:
            raise HomeAssistantError(f"Command failed: {err}") from err
        if on_sent is not None:
            on_sent()
        await self.coordinator.async_request_refresh()

    async def async_start(self) -> None:
        device = self._device
        pin = self.coordinator.pin
        if device.requires_pin and not pin:
            raise HomeAssistantError(
                "This mower requires its PIN code to start. "
                "Set it in the Cramer Connect integration options."
            )
        await self._async_command(build_start_command(pin if device.requires_pin else None))

    async def async_stop(self) -> None:
        await self._async_command(build_stop_command(self._device))

    async def async_park(self, minutes: int | None = None) -> None:
        try:
            payload = build_park_command(minutes)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        await self._async_command(payload)


def timer_from_times(start: dt_time | None, end: dt_time | None) -> ScheduleTimer:
    """Build a timer from start/end times; end 00:00 means midnight."""
    if start is None and end is None:
        return OFF_TIMER
    if start is None or end is None:
        raise HomeAssistantError("A timer needs both a start and an end time")
    start_min = start.hour * 60 + start.minute
    end_min = end.hour * 60 + end.minute
    if end_min == 0:
        end_min = 24 * 60
    if end_min <= start_min:
        raise HomeAssistantError("A timer's end time must be after its start time")
    return ScheduleTimer(start.hour, start.minute, end_min - start_min, True)


class CramerScheduleMixin:
    """Schedule settings, mirroring the app's Schedule screen."""

    async def async_set_schedule(
        self: CramerMowerEntity,
        days: list[str],
        timer_1_start: dt_time | None = None,
        timer_1_end: dt_time | None = None,
        timer_2_start: dt_time | None = None,
        timer_2_end: dt_time | None = None,
    ) -> None:
        """Set the timers of the given days; other days keep their timers."""
        timers = (
            timer_from_times(timer_1_start, timer_1_end),
            timer_from_times(timer_2_start, timer_2_end),
        )
        unknown = set(days) - set(SCHEDULE_DAYS)
        if unknown or not days:
            raise HomeAssistantError(f"Invalid days: {sorted(unknown) or days}")
        current = self._device.schedule
        if current is None and set(days) != set(SCHEDULE_DAYS):
            raise HomeAssistantError(
                "The current schedule is unknown; set all seven days at once"
            )
        schedule = tuple(
            timers if day in days else current[i]
            for i, day in enumerate(SCHEDULE_DAYS)
        )
        try:
            payload = build_schedule_command(schedule)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        await self._async_command(
            payload,
            on_sent=lambda: self.coordinator.set_pending_schedule(
                self._device_id, schedule
            ),
        )

    async def async_start_nonstop_mowing(self: CramerMowerEntity, days: int) -> None:
        try:
            payload = build_nonstop_command(days)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        await self._async_command(payload)

    async def async_cancel_nonstop_mowing(self: CramerMowerEntity) -> None:
        await self._async_command(build_nonstop_command(None))

    async def async_set_clock(self: CramerMowerEntity) -> None:
        """Set the mower clock to Home Assistant's time and time zone."""
        now = dt_util.now()
        offset = int(now.utcoffset().total_seconds()) if now.utcoffset() else 0
        await self._async_command(
            build_set_clock_command(int(now.timestamp()), offset)
        )


def remotely_controllable(device: CramerDevice) -> bool:
    return device.is_mower and device.supports_remote_control
