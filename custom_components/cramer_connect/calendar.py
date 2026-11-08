"""Mowing schedule calendar for Cramer Connect (weekly timers from dp[125])."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import Schedule
from .const import DOMAIN
from .coordinator import CramerConnectCoordinator
from .entity import CramerMowerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CramerConnectCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        CramerScheduleCalendar(coordinator, device_id)
        for device_id, device in coordinator.data.items()
        if device.is_mower
    )


def schedule_events(
    schedule: Schedule, start: datetime, end: datetime
) -> list[CalendarEvent]:
    """Expand the weekly timers into events overlapping [start, end)."""
    tz = dt_util.get_default_time_zone()
    events: list[CalendarEvent] = []
    # Start a day early so a window that began yesterday is included
    day: date = dt_util.as_local(start).date() - timedelta(days=1)
    last: date = dt_util.as_local(end).date()
    while day <= last:
        for n, timer in enumerate(schedule[day.weekday()], start=1):
            if not timer.active:
                continue
            ev_start = datetime.combine(
                day, time(timer.start_hour, timer.start_minute), tzinfo=tz
            )
            ev_end = ev_start + timedelta(minutes=timer.length_minutes)
            if ev_end > start and ev_start < end:
                events.append(
                    CalendarEvent(
                        start=ev_start,
                        end=ev_end,
                        summary="Mowing",
                        description=f"Timer {n}",
                    )
                )
        day += timedelta(days=1)
    events.sort(key=lambda e: e.start)
    return events


class CramerScheduleCalendar(CramerMowerEntity, CalendarEntity):
    _attr_translation_key = "schedule"

    def __init__(self, coordinator: CramerConnectCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_schedule"

    @property
    def available(self) -> bool:
        # The last known schedule stays valid while the mower is offline
        return (
            self._device_id in self.coordinator.data
            and self._device.schedule is not None
        )

    @property
    def event(self) -> CalendarEvent | None:
        """The current window, or the next one within a week."""
        schedule = self._device.schedule
        if schedule is None:
            return None
        now = dt_util.now()
        events = schedule_events(schedule, now, now + timedelta(days=8))
        return events[0] if events else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        schedule = self._device.schedule
        if schedule is None:
            return []
        return schedule_events(schedule, start_date, end_date)

    @property
    def extra_state_attributes(self) -> dict:
        device = self._device
        return {"nonstop_mowing": device.nonstop_mowing}
