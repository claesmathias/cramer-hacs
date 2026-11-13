"""DataUpdateCoordinator for Cramer Connect."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    CramerAuth,
    CramerConnectApiError,
    CramerConnectAuthError,
    CramerConnectClient,
    CramerConnectTokenExpiredError,
    CramerDevice,
    Schedule,
)
from .const import DOMAIN, SCAN_INTERVAL_SECONDS

# How long a just-written schedule wins over the (possibly stale) cloud copy
PENDING_SCHEDULE_TTL_S = 120

_LOGGER = logging.getLogger(__name__)


class CramerConnectCoordinator(DataUpdateCoordinator[dict[str, CramerDevice]]):
    def __init__(
        self,
        hass: HomeAssistant,
        client: CramerConnectClient,
        auth: CramerAuth,
        username: str,
        password: str,
        pin: str | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self._client = client
        self._auth = auth
        self._username = username
        self._password = password
        self.pin = pin or None
        # device_id -> (schedule written by us, monotonic expiry)
        self._pending_schedules: dict[str, tuple[Schedule, float]] = {}
        # Serializes logins: a button press and a refresh can both need one
        self._auth_lock = asyncio.Lock()

    @property
    def client(self) -> CramerConnectClient:
        return self._client

    @property
    def auth(self) -> CramerAuth:
        return self._auth

    async def _async_update_data(self) -> dict[str, CramerDevice]:
        await self._ensure_auth()
        try:
            devices = await self._client.get_devices(self._auth)
        except CramerConnectAuthError:
            # Token rejected before its nominal expiry — log in again once.
            await self.force_reauth()
            try:
                devices = await self._client.get_devices(self._auth)
            except CramerConnectAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except CramerConnectApiError as err:
                raise UpdateFailed(str(err)) from err
        except CramerConnectApiError as err:
            raise UpdateFailed(str(err)) from err

        data = {d.device_id: d for d in devices}
        self._apply_pending_schedules(data)
        return data

    def _apply_pending_schedules(self, data: dict[str, CramerDevice]) -> None:
        now = time.monotonic()
        for device_id, (schedule, expires) in list(self._pending_schedules.items()):
            device = data.get(device_id)
            if device is None or now > expires or device.schedule == schedule:
                del self._pending_schedules[device_id]
            else:
                device.schedule = schedule

    def set_pending_schedule(self, device_id: str, schedule: Schedule) -> None:
        """Show a schedule we just sent until the cloud reports it."""
        self._pending_schedules[device_id] = (
            schedule, time.monotonic() + PENDING_SCHEDULE_TTL_S,
        )
        if self.data and device_id in self.data:
            self.data[device_id].schedule = schedule
            self.async_update_listeners()

    async def async_send_command(self, device_id: str, payload_hex: str) -> None:
        """Send an MQTT command, re-authenticating once if it is refused."""
        try:
            await self._client.send_command(self._auth, device_id, payload_hex)
        except CramerConnectTokenExpiredError:
            _LOGGER.debug("MQTT login refused, re-authenticating and retrying")
            await self.force_reauth()
            await self._client.send_command(self._auth, device_id, payload_hex)

    async def force_reauth(self) -> None:
        """Re-authenticate and update stored tokens.

        Concurrent callers share one login: whoever waited for the lock
        while another caller logged in reuses that fresh session.
        """
        stale = self._auth
        async with self._auth_lock:
            if self._auth is not stale:
                return  # someone else already logged in
            _LOGGER.debug("Re-authenticating")
            try:
                self._auth = await self._client.authenticate(
                    self._username, self._password
                )
            except CramerConnectAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except CramerConnectApiError as err:
                raise UpdateFailed(str(err)) from err

    async def _ensure_auth(self) -> None:
        age = (datetime.now() - self._auth.fetched_at).total_seconds()
        # auth.expires_in accounts for both the GUC and the xlink token
        # (xlink tokens expire after 2 h regardless of the GUC lifetime).
        if age < self._auth.expires_in - 60:
            return
        _LOGGER.debug("Token expiring, re-authenticating")
        await self.force_reauth()
