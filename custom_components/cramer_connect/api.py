"""Cramer Connect API client."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import aiohttp

from .const import (
    APP_APPLICATION_KEY,
    APP_BRAND,
    APP_NAME,
    FLEET_API_URL,
    FLEET_AUTH_URL,
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
    fetched_at: datetime = field(default_factory=datetime.now)


class CramerConnectApiError(Exception):
    pass


class CramerConnectAuthError(CramerConnectApiError):
    pass


def _base_headers() -> dict[str, str]:
    """Headers the app sends on every request."""
    return {
        "ApplicationKey": APP_APPLICATION_KEY,
        "Brand": APP_BRAND,
        "App-Name": APP_NAME,
        "Language": "en",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


class CramerConnectClient:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def authenticate(self, username: str, password: str) -> CramerAuth:
        """Full login flow: fleet login → get GUC token via fleet API."""
        fleet_token, organization_id = await self._fleet_login(username, password)
        guc_token, guc_refresh_token, guc_expires_in = await self._get_guc_token(
            fleet_token, organization_id
        )
        return CramerAuth(
            fleet_token=fleet_token,
            guc_token=guc_token,
            guc_refresh_token=guc_refresh_token,
            organization_id=organization_id,
            guc_expires_in=guc_expires_in,
        )

    async def refresh_guc_token(
        self, fleet_token: str, organization_id: str
    ) -> tuple[str, str, int]:
        """Re-fetch a GUC token using the fleet token."""
        return await self._get_guc_token(fleet_token, organization_id)

    async def get_devices(self, auth: CramerAuth) -> list[CramerDevice]:
        url = f"{FLEET_API_URL}/api/devices/{auth.organization_id}/subscribed"
        headers = {**_base_headers(), "Authorization": f"Bearer {auth.fleet_token}"}
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
        headers = {**_base_headers(), "Authorization": f"Bearer {auth.fleet_token}"}
        async with self._session.get(url, headers=headers) as resp:
            if resp.status == 401:
                raise CramerConnectAuthError("Fleet token expired or invalid")
            if resp.status != 200:
                text = await resp.text()
                raise CramerConnectApiError(
                    f"Failed to get device status ({resp.status}): {text}"
                )
            return await resp.json()

    async def _fleet_login(self, username: str, password: str) -> tuple[str, str]:
        """Returns (fleet_access_token, organization_id).

        The app first calls /api/Authorization/user-exist to decide which login
        path to use. For Cramer Connect users the fleet path is always taken, so
        we go directly to /api/Authenticate.
        """
        url = f"{FLEET_API_URL}/api/Authenticate"
        payload = {"username": username, "password": password}
        async with self._session.post(url, json=payload, headers=_base_headers()) as resp:
            if resp.status in (400, 401, 403):
                text = await resp.text()
                _LOGGER.debug("Fleet login %s: %s", resp.status, text)
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

        # Prefer owner_organization_id when present (sub-org members)
        org_id = data.get("owner_organization_id") or data.get("organization_id", "")
        return token, org_id

    async def _get_guc_token(
        self, fleet_token: str, organization_id: str
    ) -> tuple[str, str, int]:
        """Exchange the fleet token for a GUC token via the fleet API.

        Returns (access_token, refresh_token, expires_in_seconds).
        """
        url = f"{FLEET_API_URL}/api/account/GucToken"
        payload = {"organizationId": organization_id}
        headers = {**_base_headers(), "Authorization": f"Bearer {fleet_token}"}
        async with self._session.post(url, json=payload, headers=headers) as resp:
            if resp.status == 401:
                raise CramerConnectAuthError("Fleet token rejected by GucToken endpoint")
            if resp.status != 200:
                text = await resp.text()
                raise CramerConnectApiError(
                    f"GucToken request failed ({resp.status}): {text}"
                )
            data = await resp.json()

        token = data.get("accessToken")
        if not token:
            raise CramerConnectAuthError("No accessToken in GucToken response")

        refresh = data.get("refreshToken", "")
        expires_in = int(data.get("expireIn", 3600))
        return token, refresh, expires_in
