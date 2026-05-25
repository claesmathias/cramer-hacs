"""DataUpdateCoordinator for Cramer Connect."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    CramerAuth,
    CramerConnectAuthError,
    CramerConnectApiError,
    CramerConnectClient,
    CramerDevice,
)
from .const import DOMAIN, SCAN_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


class CramerConnectCoordinator(DataUpdateCoordinator[dict[str, CramerDevice]]):
    def __init__(
        self,
        hass: HomeAssistant,
        client: CramerConnectClient,
        auth: CramerAuth,
        username: str,
        password: str,
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

    async def _async_update_data(self) -> dict[str, CramerDevice]:
        await self._ensure_auth()
        try:
            devices = await self._client.get_devices(self._auth)
        except CramerConnectAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except CramerConnectApiError as err:
            raise UpdateFailed(str(err)) from err

        return {d.device_id: d for d in devices}

    async def _ensure_auth(self) -> None:
        guc_age = (datetime.now() - self._auth.fetched_at).total_seconds()
        if guc_age < self._auth.guc_expires_in - 60:
            return

        _LOGGER.debug("GUC token expiring, refreshing")
        try:
            token, refresh, expires_in = await self._client.refresh_guc_token(
                self._auth.guc_refresh_token
            )
            self._auth.guc_token = token
            self._auth.guc_refresh_token = refresh
            self._auth.guc_expires_in = expires_in
            self._auth.fetched_at = datetime.now()
        except CramerConnectAuthError:
            _LOGGER.info("Token refresh failed, re-authenticating")
            try:
                self._auth = await self._client.authenticate(
                    self._username, self._password
                )
            except CramerConnectAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
