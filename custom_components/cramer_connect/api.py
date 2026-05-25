"""Cramer Connect API client."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import aiohttp

from .const import (
    FLEET_API_URL,
    FLEET_AUTH_URL,
    GUC_CLIENT_ID,
    GUC_CLIENT_SECRET,
    GUC_SCOPE,
    GUC_URL,
    MOWER_STATE_MAP,
    ROBOTIC_MOWER_PRODUCT_CODES,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class CramerDevice:
    device_id: str
    product_id: str
    name: str
    serial_number: str
    mac: str
    product_code: str
    state: str | None
    battery: int | None
    is_online: bool
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def state_label(self) -> str:
        return MOWER_STATE_MAP.get(self.state or "", "unknown")

    @property
    def is_mower(self) -> bool:
        return self.product_code in ROBOTIC_MOWER_PRODUCT_CODES


@dataclass
class CramerAuth:
    fleet_token: str
    guc_token: str
    guc_refresh_token: str
    organization_id: str
    guc_expires_in: int
    fleet_expiration: str | None
    fetched_at: datetime = field(default_factory=datetime.now)


class CramerConnectApiError(Exception):
    pass


class CramerConnectAuthError(CramerConnectApiError):
    pass


class CramerConnectClient:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def authenticate(self, username: str, password: str) -> CramerAuth:
        fleet_token, organization_id, fleet_expiration = await self._fleet_login(
            username, password
        )
        guc_token, guc_refresh_token, guc_expires_in = await self._guc_login(
            username, password
        )
        return CramerAuth(
            fleet_token=fleet_token,
            guc_token=guc_token,
            guc_refresh_token=guc_refresh_token,
            organization_id=organization_id,
            guc_expires_in=guc_expires_in,
            fleet_expiration=fleet_expiration,
        )

    async def refresh_guc_token(self, refresh_token: str) -> tuple[str, str, int]:
        """Refresh GUC token. Returns (access_token, refresh_token, expires_in)."""
        url = "https://xapi.globetools.systems/v2/user/token/refresh"
        payload = {"refresh_token": refresh_token}
        async with self._session.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                _LOGGER.warning("GUC token refresh failed (%s): %s", resp.status, text)
                raise CramerConnectAuthError(f"Token refresh failed: {resp.status}")
            data = await resp.json()
            return (
                data["access_token"],
                data.get("refresh_token", refresh_token),
                int(data.get("expires_in", 3600)),
            )

    async def get_devices(self, auth: CramerAuth) -> list[CramerDevice]:
        url = f"{FLEET_API_URL}/api/devices/{auth.organization_id}/subscribed"
        headers = {
            "Authorization": f"Bearer {auth.fleet_token}",
            "Content-Type": "application/json",
        }
        async with self._session.get(url, headers=headers) as resp:
            if resp.status == 401:
                raise CramerConnectAuthError("Fleet token expired or invalid")
            if resp.status != 200:
                text = await resp.text()
                raise CramerConnectApiError(
                    f"Failed to get devices ({resp.status}): {text}"
                )
            data: list[dict] = await resp.json()

        devices = []
        for item in data or []:
            product_model = item.get("productModel") or {}
            product_code = item.get("productCode") or product_model.get("productCode", "")
            devices.append(
                CramerDevice(
                    device_id=str(item.get("id", "")),
                    product_id=str(item.get("product_id", "")),
                    name=item.get("name") or item.get("batteryPropertyName") or "Cramer Mower",
                    serial_number=item.get("sn", ""),
                    mac=item.get("mac", ""),
                    product_code=product_code,
                    state=str(item["state"]) if item.get("state") is not None else None,
                    battery=item.get("battery"),
                    is_online=bool(item.get("is_online", False)),
                    raw=item,
                )
            )
        return devices

    async def get_device_status(
        self, auth: CramerAuth, product_id: str, device_id: str
    ) -> dict[str, Any]:
        url = (
            f"{FLEET_API_URL}/api/devices/{auth.organization_id}"
            f"/status/{product_id}/{device_id}"
        )
        headers = {
            "Authorization": f"Bearer {auth.fleet_token}",
            "Content-Type": "application/json",
        }
        async with self._session.get(url, headers=headers) as resp:
            if resp.status == 401:
                raise CramerConnectAuthError("Fleet token expired or invalid")
            if resp.status != 200:
                text = await resp.text()
                raise CramerConnectApiError(
                    f"Failed to get device status ({resp.status}): {text}"
                )
            return await resp.json()

    async def _fleet_login(
        self, username: str, password: str
    ) -> tuple[str, str, str | None]:
        """Returns (access_token, organization_id, expiration)."""
        url = f"{FLEET_API_URL}/api/Authenticate"
        payload = {"username": username, "password": password}
        async with self._session.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        ) as resp:
            if resp.status in (401, 403):
                raise CramerConnectAuthError("Invalid credentials")
            if resp.status != 200:
                text = await resp.text()
                raise CramerConnectApiError(
                    f"Fleet login failed ({resp.status}): {text}"
                )
            data = await resp.json()

        token = data.get("access_token")
        if not token:
            raise CramerConnectAuthError("No access_token in fleet login response")

        org_id = data.get("organization_id", "")
        expiration = data.get("expiration")
        return token, org_id, expiration

    async def _guc_login(
        self, username: str, password: str
    ) -> tuple[str, str, int]:
        """Returns (access_token, refresh_token, expires_in)."""
        url = f"{GUC_URL}/connect/token"
        payload = {
            "scope": GUC_SCOPE,
            "grant_type": "password",
            "client_id": GUC_CLIENT_ID,
            "client_secret": GUC_CLIENT_SECRET,
            "username": username,
            "password": password,
            "HasLocationInfo": "false",
            "Latitude": "0",
            "Longitude": "0",
            "LoginTime": str(int(datetime.now().timestamp())),
        }
        async with self._session.post(
            url,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ) as resp:
            if resp.status in (400, 401, 403):
                text = await resp.text()
                raise CramerConnectAuthError(
                    f"GUC login failed ({resp.status}): {text}"
                )
            if resp.status != 200:
                text = await resp.text()
                raise CramerConnectApiError(
                    f"GUC login failed ({resp.status}): {text}"
                )
            data = await resp.json()

        token = data.get("access_token")
        refresh = data.get("refresh_token", "")
        expires_in = int(data.get("expires_in", 3600))
        if not token:
            raise CramerConnectAuthError("No access_token in GUC login response")
        return token, refresh, expires_in
